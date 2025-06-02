import os
import time
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_db_session
from app.db.session import Base
from app.main import app

TEST_DATABASE_NAME = "smartpay_test"
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", f"postgresql+asyncpg://postgres:postgres@smartpay-postgres-dev:5432/{TEST_DATABASE_NAME}"
)

os.environ["ENABLE_TRACING"] = "false"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_test_db():
    admin_dsn = os.getenv("TEST_ADMIN_DSN", "postgresql://postgres:postgres@smartpay-postgres-dev:5432/postgres")
    for i in range(10):
        try:
            conn = await asyncpg.connect(dsn=admin_dsn)
            await conn.close()
            break
        except Exception as e:
            print(f"Waiting for Postgres... ({i+1}/10): {e}")
            time.sleep(2)
    else:
        raise RuntimeError("Could not connect to Postgres for test DB setup")

    conn = await asyncpg.connect(dsn=admin_dsn)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DATABASE_NAME}" WITH (FORCE);')
        await conn.execute(f'CREATE DATABASE "{TEST_DATABASE_NAME}";')
        print(f"✅ Created test database: {TEST_DATABASE_NAME}")
    finally:
        await conn.close()
    yield
    conn = await asyncpg.connect(dsn=admin_dsn)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DATABASE_NAME}" WITH (FORCE);')
        print(f"🧹 Dropped test database: {TEST_DATABASE_NAME}")
    finally:
        await conn.close()


@pytest_asyncio.fixture(scope="function")
async def db_session(prepare_test_db) -> AsyncGenerator[AsyncSession, None]:
    # Create engine and sessionmaker inside the fixture
    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    test_async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with test_async_session() as session:
        yield session
    # Drop all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def mock_redis() -> AsyncGenerator[AsyncMock, None]:
    mock_client = AsyncMock()
    mock_client.ping.return_value = True
    mock_client.get.return_value = "mock_value"
    mock_client.set.return_value = True
    mock_client.delete.return_value = 1
    mock_client.exists.return_value = 1
    mock_client.incr.return_value = 1
    mock_client.decr.return_value = 0
    yield mock_client


@pytest_asyncio.fixture(scope="function")
async def mock_kafka() -> AsyncGenerator[AsyncMock, None]:
    mock_producer = AsyncMock()
    mock_producer.connected.return_value = True
    mock_producer.start.return_value = None
    mock_producer.send_message.return_value = {"status": "sent", "topic": "test_topic"}
    yield mock_producer


@pytest_asyncio.fixture(scope="function")
async def client(
    db_session: AsyncSession, mock_redis: AsyncMock, mock_kafka: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides = {}

"""
Test fixtures.
"""

import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock

import asyncpg
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_db_session
from app.db.session import Base
from app.main import app

# Test database URL
TEST_DATABASE_NAME = "smartpay_test"

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", f"postgresql+asyncpg://postgres:postgres@smartpay-postgres:5432/{TEST_DATABASE_NAME}"
)

# Disable tracing for tests
os.environ["ENABLE_TRACING"] = "false"

# Create async engine for testing
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

# Create async session factory
test_async_session = sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_test_db() -> AsyncGenerator[None, None]:
    """
    Create the test database before tests run, and drop it after tests.
    """
    admin_dsn = "postgresql://postgres:postgres@smartpay-postgres:5432/postgres"

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


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """
    Create an instance of the default event loop for each test case.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Create a clean database session for a test.

    Yields a clean session for test, and cleans up after.
    """
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async with test_async_session() as session:
        yield session

    # Clean up - drop all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def mock_redis() -> AsyncGenerator[AsyncMock, None]:
    """
    Create a mock Redis client for testing.
    """
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
    """
    Create a mock Kafka producer for testing.
    """
    mock_producer = AsyncMock()
    mock_producer.connected.return_value = True
    mock_producer.start.return_value = None
    mock_producer.send_message.return_value = {"status": "sent", "topic": "test_topic"}
    yield mock_producer


@pytest_asyncio.fixture(scope="function")
async def client(
    db_session: AsyncSession, mock_redis: AsyncMock, mock_kafka: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create a test client for the FastAPI application.
    """
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides = {}

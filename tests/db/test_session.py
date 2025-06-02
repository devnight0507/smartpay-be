import os

import pytest

from app.db import session


def test_database_url_env(monkeypatch):
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg://test/test")
    # Reload module to pick up env var
    import importlib

    import app.db.session as session_mod

    importlib.reload(session_mod)
    assert "test" in session_mod.engine.url.database


@pytest.mark.asyncio
async def test_get_db_yields_session():
    async_gen = session.get_db()
    session_obj = await async_gen.__anext__()
    from sqlalchemy.ext.asyncio import AsyncSession

    assert isinstance(session_obj, AsyncSession)
    # Clean up generator
    try:
        await async_gen.__anext__()
    except StopAsyncIteration:
        pass

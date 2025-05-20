"""
Application lifecycle event handlers.

These functions are executed during application startup and shutdown.
"""

from typing import Callable, List

from loguru import logger
from app.core.config import settings
from app.db.session import engine

async def connect_to_db() -> None:
    """
    Initialize database connection.
    """
    try:
        # Test database connection to fail fast during startup if DB is not available
        logger.info("Connecting to PostgreSQL database...")

        from sqlalchemy import text

        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            await session.commit()

        logger.info("Database connection established and verified")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        # Critical error - fail application startup if database is not available
        raise


async def close_db_connection() -> None:
    """
    Close database connection.
    """
    try:
        logger.info("Closing database connections...")
        await engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


# List of startup event handlers to be executed in order
startup_event_handlers: List[Callable] = [
    connect_to_db,
]

# List of shutdown event handlers to be executed in order
shutdown_event_handlers: List[Callable] = [
    close_db_connection,
]

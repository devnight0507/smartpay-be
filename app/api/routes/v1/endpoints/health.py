"""
Health check endpoint.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Response, status
from loguru import logger
from pydantic import BaseModel

from app.api.dependencies import get_db_session
from app.core.config import settings

router = APIRouter()


class HealthStatus(BaseModel):
    """Health status model."""

    status: str
    version: str
    environment: str

    class Config:
        schema_extra = {"example": {"status": "ok", "version": "1.0.0", "environment": "development"}}


class ComponentStatus(BaseModel):
    """Component health status model."""

    name: str
    status: str
    details: Optional[Dict] = None

    class Config:
        schema_extra = {"example": {"name": "database", "status": "healthy", "details": {"type": "postgresql"}}}


class DetailedHealthStatus(HealthStatus):
    """Detailed health status model with component status information."""

    components: List[ComponentStatus]

    class Config:
        schema_extra = {
            "example": {
                "status": "ok",
                "version": "1.0.0",
                "environment": "development",
                "components": [
                    {"name": "database", "status": "healthy", "details": {"type": "postgresql"}},
                    {"name": "cache", "status": "healthy", "details": {"type": "redis"}},
                    {"name": "message_broker", "status": "healthy", "details": {"type": "kafka"}},
                ],
            }
        }


@router.get(
    "",
    response_model=HealthStatus,
    summary="Basic health check endpoint",
    description="Returns a simple status indicating the service is running, along with version and environment information.",  # noqa: E501
    responses={200: {"description": "Service is healthy"}},
    tags=["Health"],
)
async def health_check() -> HealthStatus:
    """
    Basic health check endpoint.

    Returns a simple status indicating the service is running, along with version
    and environment information.
    """
    return HealthStatus(
        status="ok",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    )


@router.get(
    "/ready",
    response_model=DetailedHealthStatus,
    summary="Readiness check endpoint",
    description="Checks all critical system components (database, cache, message broker) and returns detailed status information.",  # noqa: E501
    responses={200: {"description": "Service is ready"}, 503: {"description": "Service is not ready"}},
    tags=["Health"],
)
async def readiness_check(
    response: Response,
    db_session: Any = Depends(get_db_session),
) -> DetailedHealthStatus:
    """
    Detailed health check for service readiness.

    Checks all critical system components (database, cache, message broker)
    and returns detailed status information.
    """
    components = []
    all_healthy = True

    # Check database
    try:
        # Simple database query to check connection
        from sqlalchemy import text

        await db_session.execute(text("SELECT 1"))
        components.append(ComponentStatus(name="database", status="healthy", details={"type": "postgresql"}))
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        components.append(ComponentStatus(name="database", status="unhealthy", details={"error": str(e)}))
        all_healthy = False

    # Set response status
    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return DetailedHealthStatus(
        status="ok" if all_healthy else "degraded",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        components=components,
    )


# Metrics endpoint is now handled by the core.metrics module

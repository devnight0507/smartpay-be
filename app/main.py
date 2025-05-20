"""
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from app.api.errors import register_exception_handlers
from app.api.middleware import TranslationMiddleware
from app.api.routes.v1.endpoints.errors import router as errors_router
from app.api.routes.v1.endpoints.health import router as health_router
from app.api.routes.v1.endpoints.websockets.notifications import (
    router as websocket_router,
)
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.metrics import setup_metrics
from app.core.tracing import setup_tracing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan event handler for startup and shutdown events.
    """
    # Configure Sentry
    if settings.SENTRY_DSN:
        sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[
                FastApiIntegration(),
                sentry_logging,
            ],
            environment=settings.ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            release=f"{settings.PROJECT_NAME}@{settings.VERSION}",
        )
        logger.info("Sentry initialized")

    yield


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    configure_logging()

    application = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        docs_url="/api/docs" if not settings.ENVIRONMENT == "production" else None,
        redoc_url="/api/redoc" if not settings.ENVIRONMENT == "production" else None,
        openapi_url="/api/openapi.json" if not settings.ENVIRONMENT == "production" else None,
        lifespan=lifespan,
        swagger_ui_parameters={
            "deepLinking": True,
            "displayRequestDuration": True,
            "filter": True,
            "tryItOutEnabled": True,
            "syntaxHighlight.theme": "monokai",
        },
        openapi_tags=[
            {"name": "Health", "description": "Health check and readiness endpoints"},
            {"name": "Items", "description": "Item management endpoints"},
            {"name": "Job Consumer", "description": "Job queue and execution endpoints"},
            {"name": "Errors", "description": "Error demonstration endpoints with i18n support"},
            {"name": "WebSockets", "description": "WebSocket connection and notification endpoints"},
        ],
        contact={
            "name": "API Support",
            "email": "support@example.com",
            "url": "https://example.com/support",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
    )

    # Register exception handlers
    register_exception_handlers(application)

    # Add CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.CORS_ORIGINS_STR == "*" else settings.CORS_ORIGINS_STR.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add Translation middleware for i18n support
    application.add_middleware(TranslationMiddleware)

    # Setup Prometheus metrics middleware if enabled
    if settings.ENABLE_METRICS:
        setup_metrics(application)
        logger.info("Prometheus metrics enabled")

    # Setup OpenTelemetry tracing if enabled
    if settings.ENABLE_TRACING:
        setup_tracing(application)
        logger.info("OpenTelemetry tracing enabled")

    # Include routers
    application.include_router(health_router, prefix="/api/health", tags=["Health"])
    application.include_router(errors_router, prefix="/api/v1", tags=["Errors"])
    application.include_router(websocket_router, prefix="/api/v1/ws", tags=["WebSockets"])

    return application


app = create_application()

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
from app.api.routes.v1.admin import router as admin_router
from app.api.routes.v1.auth import router as auth_router
from app.api.routes.v1.endpoints.errors import router as errors_router
from app.api.routes.v1.endpoints.health import router as health_router
from app.api.routes.v1.notifications import router as notification_router
from app.api.routes.v1.paymentCard import router as paymentCard_router
from app.api.routes.v1.profile import router as profile_router
from app.api.routes.v1.wallet import router as wallet_router
from app.api.websockets.notifications_ws import router as socket_router
from app.core.config import settings
from app.core.logging import configure_logging


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
        docs_url="/api/docs",  # if not settings.ENVIRONMENT == "production" else None,
        redoc_url="/api/redoc",  # if not settings.ENVIRONMENT == "production" else None,
        openapi_url="/api/openapi.json",  # if not settings.ENVIRONMENT == "production" else None,
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
            {"name": "Auth", "description": "Authentication endpoints"},
            {"name": "Profile", "description": "Profile endpoints"},
            {"name": "Admin", "description": "Admin management endpoints"},
            {"name": "Wallet", "description": "Wallet check endpoints"},
            {"name": "Payment Card", "description": "Payment card endpoints"},
            {"name": "Errors", "description": "Error demonstration endpoints with i18n support"},
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

    cors_origins = ["*"] if settings.CORS_ORIGINS_STR == "*" else settings.CORS_ORIGINS_STR.split(",")

    cors_origins.extend(
        [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "http://146.19.215.133:5000",
            "https://smartpay.lavendarsolution.com",
            "http://smartpay.lavendarsolution.com",
        ]
    )
    # Add CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add Translation middleware for i18n support
    application.add_middleware(TranslationMiddleware)

    # Include routers
    application.include_router(health_router, prefix="/api/health", tags=["Health"])
    application.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
    application.include_router(profile_router, prefix="/api/v1/profile", tags=["Profile"])
    application.include_router(wallet_router, prefix="/api/v1/wallet", tags=["Wallet"])
    application.include_router(notification_router, prefix="/api/v1/notification", tags=["Notification"])
    # application.include_router(notification_setting_router, prefix="/api/v1/notification_setting", tags=["Wallet"])
    application.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])
    application.include_router(paymentCard_router, prefix="/api/v1/payment-cards", tags=["Payment Card"])
    application.include_router(errors_router, prefix="/api/v1", tags=["Errors"])
    application.include_router(socket_router, tags=["WebSockets"])
    application.get("/test-mail/")

    return application


app = create_application()

"""
API middleware components.

This module contains middleware components for the API, including
translation support, request ID generation, and more.
"""

import contextvars
import uuid
from typing import Optional

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from app.api.i18n import SupportedLanguage, get_preferred_language

# Context variables for request-scoped data
request_id_var = contextvars.ContextVar[Optional[str]]("request_id", default=None)
language_var = contextvars.ContextVar[SupportedLanguage]("language", default=SupportedLanguage.get_default())


class TranslationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract the Accept-Language header and set the language for the request.

    This middleware also sets a request ID for correlation in logs and adds headers
    to the response for language and request ID.
    """

    def __init__(self, app: ASGIApp, default_language: SupportedLanguage = SupportedLanguage.get_default()):
        """
        Initialize the middleware.

        Args:
            app: The ASGI application
            default_language: The default language to use when no Accept-Language header is present
        """
        super().__init__(app)
        self.default_language = default_language

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Process a request and extract language information.

        Args:
            request: The FastAPI request
            call_next: The next request handler

        Returns:
            The response
        """
        # Generate a request ID for correlation
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)

        # Extract preferred language from Accept-Language header
        language = get_preferred_language(request)
        language_var.set(language)

        # Log request with language and request ID
        logger.info(
            f"Request {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "language": language.value,
                "method": request.method,
                "path": request.url.path,
                "client_host": request.client.host if request.client else None,
            },
        )

        # Process the request
        response = await call_next(request)

        # Add headers to the response
        response.headers["X-Request-ID"] = request_id
        response.headers["Content-Language"] = language.value

        return response


def get_request_language() -> SupportedLanguage:
    """
    Get the language for the current request.

    Returns:
        The current request language
    """
    return language_var.get()


def get_request_id() -> str:
    """
    Get the request ID for the current request.

    Returns:
        The current request ID or an empty string if not in a request context
    """
    request_id = request_id_var.get()
    return request_id if request_id is not None else ""

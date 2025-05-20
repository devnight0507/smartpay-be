"""
API error handling for consistent error responses across the application.
"""

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


class ErrorResponse(BaseModel):
    """Standardized error response model."""

    error: Dict[str, Any]


class ErrorDetail(BaseModel):
    """Error detail model."""

    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register exception handlers for the FastAPI application.
    """

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """
        Handle validation errors and return a standardized response.
        """
        logger.warning(f"Validation error: {exc.errors()}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request parameters",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        """
        Handle database integrity errors.
        """
        logger.error(f"Database integrity error: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": "DATABASE_INTEGRITY_ERROR",
                    "message": "Database constraint violation",
                    "details": {"error": str(exc)},
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        """
        Handle general SQLAlchemy errors.
        """
        logger.error(f"Database error: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "A database error occurred",
                    "details": {"error": str(exc)},
                }
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Handle all other uncaught exceptions.
        """
        logger.exception(f"Unhandled exception: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {"error": str(exc)},
                }
            },
        )


def create_error_response(
    error_code: str, message: str, details: Optional[Dict[str, Any]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Create a standardized error response.
    """
    return {"error": {"code": error_code, "message": message, "details": details}}

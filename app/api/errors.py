"""
API error handling for consistent error responses across the application.
"""

from typing import Dict

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


class ErrorResponse(BaseModel):
    """Standardized error response model."""

    detail: str


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

        def flatten_error(err: dict) -> str:
            location = ".".join(str(loc) for loc in err.get("loc", []))
            message = err.get("msg", "Validation error")
            return f"{location}: {message}"

        flat_errors = [flatten_error(err) for err in exc.errors()]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": " | ".join(flat_errors)},
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
                "detail": str(exc),
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
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Handle all other uncaught exceptions.
        """
        logger.exception(f"Unhandled exception: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )


def create_error_response(error_code: str, message: str, detail: str) -> Dict[str, str]:
    """
    Create a standardized error response.
    """
    return {"detail": detail}

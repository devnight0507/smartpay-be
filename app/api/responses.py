"""
Standardized API response models and messages.

This module provides a set of standard response models and messages
for consistent API responses across the application.
"""

from enum import Enum
from typing import (  # noqa: F401
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)

from fastapi import status
from pydantic import BaseModel, Field

# Type variable for generic response models
T = TypeVar("T")


class ResponseCode(str, Enum):
    """Standard response codes for API responses."""

    SUCCESS = "success"
    ERROR = "error"
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    INTERNAL_ERROR = "internal_error"


class ResponseMessage:
    """Standard response messages with placeholders and translation support."""

    def __init__(self, message_key: str, placeholders: Optional[Dict[str, str]] = None):
        """
        Initialize a response message with optional placeholders.

        Args:
            message_key: The key of the message template
            placeholders: Optional dictionary of placeholders to fill in the template
        """
        self.message_key = message_key
        self.placeholders = placeholders or {}

    def translate(self, language: Optional[str] = None) -> str:
        """
        Translate the message to the specified language.

        Args:
            language: Language code to translate to

        Returns:
            Translated message
        """
        # Import here to avoid circular imports
        from app.api.i18n import SupportedLanguage, get_translated_message

        # Convert string language code to enum if provided
        lang = None
        if language:
            try:
                lang = SupportedLanguage(language)
            except ValueError:
                # Try to get the base language (e.g., "en-US" -> "en")
                try:
                    base_lang = language.split("-")[0]
                    lang = SupportedLanguage(base_lang)
                except (ValueError, IndexError):
                    # Fall back to default language
                    lang = SupportedLanguage.get_default()

        # Get translated message
        return get_translated_message(message_key=self.message_key, placeholders=self.placeholders, language=lang)

    @property
    def message(self) -> str:
        """Return the formatted message with placeholders filled in (default language)."""
        # Import here to avoid circular imports
        from app.api.i18n import get_translated_message

        return get_translated_message(message_key=self.message_key, placeholders=self.placeholders)

    @property
    def description(self) -> str:
        """Return the formatted message for use in OpenAPI documentation."""
        return self.message

    def __str__(self) -> str:
        """Return the formatted message as a string."""
        return self.message


class ErrorDetail(BaseModel):
    """Detail for a specific error in a validation error."""

    loc: List[str] = Field(..., description="Location of the error")
    msg: str = Field(..., description="Error message")
    type: str = Field(..., description="Error type")


class BaseResponseModel(BaseModel):
    """Base model for all API responses."""

    code: ResponseCode = Field(..., description="Response code")
    message: str = Field(..., description="Response message")


class DataResponseModel(BaseResponseModel, Generic[T]):
    """Generic response model with data."""

    data: T = Field(..., description="Response data")


class ErrorResponseModel(BaseResponseModel):
    """Base model for error responses."""

    details: Optional[Any] = Field(None, description="Additional error details")


class ValidationErrorModel(ErrorResponseModel):
    """Model for validation error responses."""

    code: ResponseCode = Field(ResponseCode.VALIDATION_ERROR, description="Validation error code")
    details: List[ErrorDetail] = Field(..., description="Validation error details")


class NotFoundModel(ErrorResponseModel):
    """Model for not found error responses."""

    code: ResponseCode = Field(ResponseCode.NOT_FOUND, description="Not found error code")


class NoContentsFoundModel(NotFoundModel):
    """Model for no contents found error responses."""

    message: str = Field(
        ResponseMessage("NoContentsFound", {"content": "records"}).message, description="No contents found message"
    )


class ForbiddenModel(ErrorResponseModel):
    """Model for forbidden error responses."""

    code: ResponseCode = Field(ResponseCode.AUTHORIZATION_ERROR, description="Authorization error code")


class JWTMalformedForbiddenModel(ForbiddenModel):
    """Model for JWT malformed forbidden error responses."""

    message: str = Field(ResponseMessage("JWTMalformedForbidden").message, description="JWT malformed message")


class InvalidAuthCredForbiddenModel(ForbiddenModel):
    """Model for invalid auth credentials forbidden error responses."""

    message: str = Field(
        ResponseMessage("InvalidAuthCredForbidden").message, description="Invalid auth credentials message"
    )


class AgentNotExistsForbiddenModel(ForbiddenModel):
    """Model for agent not exists forbidden error responses."""

    message: str = Field(ResponseMessage("AgentNotExistsForbidden").message, description="Agent not exists message")


class BadRequestModel(ErrorResponseModel):
    """Model for bad request error responses."""

    code: ResponseCode = Field(ResponseCode.ERROR, description="Bad request error code")


class AgentHasProcessingJobsModel(BadRequestModel):
    """Model for agent has processing jobs error responses."""

    message: str = Field(
        ResponseMessage("AgentHasProcessingJobs").message, description="Agent has processing jobs message"
    )


class InternalErrorModel(ErrorResponseModel):
    """Model for internal server error responses."""

    code: ResponseCode = Field(ResponseCode.INTERNAL_ERROR, description="Internal error code")
    message: str = Field(ResponseMessage("InternalError").message, description="Internal error message")


# Export HTTP status codes for easier route definitions
HTTP_200_OK = status.HTTP_200_OK
HTTP_201_CREATED = status.HTTP_201_CREATED
HTTP_204_NO_CONTENT = status.HTTP_204_NO_CONTENT
HTTP_400_BAD_REQUEST = status.HTTP_400_BAD_REQUEST
HTTP_401_UNAUTHORIZED = status.HTTP_401_UNAUTHORIZED
HTTP_403_FORBIDDEN = status.HTTP_403_FORBIDDEN
HTTP_404_NOT_FOUND = status.HTTP_404_NOT_FOUND
HTTP_409_CONFLICT = status.HTTP_409_CONFLICT
HTTP_422_UNPROCESSABLE_ENTITY = status.HTTP_422_UNPROCESSABLE_ENTITY
HTTP_500_INTERNAL_SERVER_ERROR = status.HTTP_500_INTERNAL_SERVER_ERROR


# Define tags for route categorization
class Tags:
    """API route tags for documentation grouping."""

    HEALTH = "Health"
    ITEMS = "Items"
    TAGS = "Tags"
    WEBSOCKETS = "WebSockets"
    JOB_CONSUMER = "Job Consumer"

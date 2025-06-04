"""
Error demonstration API endpoints.

These endpoints demonstrate how to use the translation system
for error responses in different languages.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query, Request
from pydantic import BaseModel

from app.api.i18n import get_preferred_language
from app.api.middleware import get_request_language
from app.api.responses import (
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorResponseModel,
    ResponseMessage,
)
from app.api.utils import create_response

router = APIRouter()


class TranslatedErrorResponse(BaseModel):
    """Translated error response model."""

    message: str
    status_code: int
    language: str


@router.get(
    "/error/{error_type}",
    response_model=TranslatedErrorResponse,
    summary="Demonstrate translated error messages",
    description="Returns a translated error message based on the Accept-Language header",
    responses={
        HTTP_400_BAD_REQUEST: {"description": "General error message"},
        HTTP_403_FORBIDDEN: {"description": "Authorization error message"},
        HTTP_404_NOT_FOUND: {"description": "Not found error message"},
        HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error message"},
    },
    tags=["Errors"],
)
async def get_error(
    request: Request,
    error_type: str = Path(
        ...,
        description="Type of error to demonstrate",
        examples=[
            {"summary": "Not Found Error", "value": "not_found"},
            {"summary": "Forbidden Error", "value": "forbidden"},
            {"summary": "Validation Error", "value": "validation"},
            {"summary": "Internal Error", "value": "internal"},
        ],
    ),
    record_type: str = Query(
        "item",
        description="Type of record to use in error message",
        examples=["item", "user", "order", "product"],
    ),
) -> TranslatedErrorResponse:
    """
    Demonstrate translated error messages.

    Args:
        request: The FastAPI request
        error_type: Type of error to demonstrate
        record_type: Type of record to use in error message

    Returns:
        A translated error response
    """
    # Get the preferred language from the request
    language = get_preferred_language(request)

    # Create the appropriate error message based on the error type
    message = None
    status_code = HTTP_400_BAD_REQUEST

    if error_type == "not_found":
        message = ResponseMessage("RecordNotFound", {"record": record_type})
        status_code = HTTP_404_NOT_FOUND
    elif error_type == "no_contents":
        message = ResponseMessage("NoContentsFound", {"content": f"{record_type}s"})
        status_code = HTTP_404_NOT_FOUND
    elif error_type == "forbidden":
        message = ResponseMessage("UnauthorizedAccess")
        status_code = HTTP_403_FORBIDDEN
    elif error_type == "validation":
        message = ResponseMessage("ValidationError")
        status_code = HTTP_400_BAD_REQUEST
    elif error_type == "internal":
        message = ResponseMessage("InternalError")
        status_code = HTTP_500_INTERNAL_SERVER_ERROR
    else:
        # Use the error_type directly as the message key
        message = ResponseMessage(error_type)

    # Translate the message to the requested language
    translated_message = message.translate(language.value)

    # Return the translated error response
    return TranslatedErrorResponse(
        message=translated_message,
        status_code=status_code,
        language=language.value,
    )


@router.get(
    "/exception/{error_type}",
    summary="Demonstrate HTTP exceptions with translated messages",
    description="Raises an HTTP exception with a translated message based on the Accept-Language header",
    responses={
        HTTP_400_BAD_REQUEST: {"description": "General error message"},
        HTTP_403_FORBIDDEN: {"description": "Authorization error message"},
        HTTP_404_NOT_FOUND: {"description": "Not found error message"},
        HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error message"},
    },
    tags=["Errors"],
    response_model=None,  # Disable response model generation
)
async def raise_exception(
    error_type: str = Path(
        ...,
        description="Type of error to demonstrate",
        examples=[
            {"summary": "Not Found Error", "value": "not_found"},
            {"summary": "Forbidden Error", "value": "forbidden"},
            {"summary": "Validation Error", "value": "validation"},
            {"summary": "Internal Error", "value": "internal"},
        ],
    ),
    record_type: str = Query(
        "item",
        description="Type of record to use in error message",
        examples=["item", "user", "order", "product"],
    ),
) -> None:
    """
    Raise an HTTP exception with a translated message.

    Args:
        error_type: Type of error to demonstrate
        record_type: Type of record to use in error message
    """
    # Get the current request language
    language = get_request_language()

    # Create the appropriate error message based on the error type
    message = None
    status_code = HTTP_400_BAD_REQUEST

    if error_type == "not_found":
        message = ResponseMessage("RecordNotFound", {"record": record_type})
        status_code = HTTP_404_NOT_FOUND
    elif error_type == "no_contents":
        message = ResponseMessage("NoContentsFound", {"content": f"{record_type}s"})
        status_code = HTTP_404_NOT_FOUND
    elif error_type == "forbidden":
        message = ResponseMessage("UnauthorizedAccess")
        status_code = HTTP_403_FORBIDDEN
    elif error_type == "validation":
        message = ResponseMessage("ValidationError")
        status_code = HTTP_400_BAD_REQUEST
    elif error_type == "internal":
        message = ResponseMessage("InternalError")
        status_code = HTTP_500_INTERNAL_SERVER_ERROR
    else:
        # Use the error_type directly as the message key
        message = ResponseMessage(error_type)

    # Translate the message to the requested language and raise an HTTP exception
    translated_message = message.translate(language.value)
    raise HTTPException(status_code=status_code, detail=translated_message)


@router.get(
    "/response/{error_type}",
    summary="Demonstrate error responses with translated messages",
    description="Returns a formatted error response with a translated message based on the Accept-Language header",
    responses={
        HTTP_400_BAD_REQUEST: {"model": ErrorResponseModel},
        HTTP_403_FORBIDDEN: {"model": ErrorResponseModel},
        HTTP_404_NOT_FOUND: {"model": ErrorResponseModel},
        HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponseModel},
    },
    tags=["Errors"],
    response_model=None,  # Disable response model generation
)
async def get_error_response(
    error_type: str = Path(
        ...,
        description="Type of error to demonstrate",
        examples=[
            {"summary": "Not Found Error", "value": "not_found"},
            {"summary": "Forbidden Error", "value": "forbidden"},
            {"summary": "Validation Error", "value": "validation"},
            {"summary": "Internal Error", "value": "internal"},
        ],
    ),
    record_type: str = Query(
        "item",
        description="Type of record to use in error message",
        examples=["item", "user", "order", "product"],
    ),
) -> Any:  # Use Any as the return type and disable response model generation
    """
    Return a formatted error response with a translated message.

    Args:
        error_type: Type of error to demonstrate
        record_type: Type of record to use in error message

    Returns:
        A formatted error response with a translated message
    """
    # Create the appropriate error response based on the error type
    if error_type == "not_found":
        # Use create_response utility
        return create_response(
            message_key="RecordNotFound",
            message_placeholders={"record": record_type},
            status_code=HTTP_404_NOT_FOUND,
            response_model=ErrorResponseModel,  # type: ignore
        )
    elif error_type == "no_contents":
        # Use create_response utility
        return create_response(
            message_key="NoContentsFound",
            message_placeholders={"content": f"{record_type}s"},
            status_code=HTTP_404_NOT_FOUND,
            response_model=ErrorResponseModel,  # type: ignore
        )
    elif error_type == "forbidden":
        # Use create_response utility
        return create_response(
            message_key="UnauthorizedAccess",
            status_code=HTTP_403_FORBIDDEN,
            response_model=ErrorResponseModel,  # type: ignore
        )
    elif error_type == "internal":
        # Use create_response utility
        return create_response(
            message_key="InternalError",
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            response_model=ErrorResponseModel,  # type: ignore
        )
    else:
        # Create a generic error response
        return create_response(
            message_key="ValidationError",
            status_code=HTTP_400_BAD_REQUEST,
            response_model=ErrorResponseModel,  # type: ignore
            data={"field": record_type, "error": error_type},
        )

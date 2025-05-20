"""
API utility functions.
"""

from typing import Any, Dict, Optional, Type, TypeVar, Union, cast

from fastapi import Response, status

from app.api.middleware import get_request_language
from app.api.responses import (
    BaseResponseModel,
    DataResponseModel,
    ErrorResponseModel,
    ResponseCode,
    ResponseMessage,
)

T = TypeVar("T")


def translate_response_message(
    response_message: ResponseMessage,
    status_code: int = status.HTTP_200_OK,
    headers: Optional[Dict[str, str]] = None,
) -> Response:
    """
    Create a translated response with the given message.

    Args:
        response_message: The response message to translate
        status_code: The HTTP status code to return
        headers: Optional headers to include in the response

    Returns:
        A FastAPI Response object with the translated message
    """
    # Get the current request language
    language = get_request_language()

    # Translate the message
    translated_message = response_message.translate(language.value)

    # Create a Response with the translated message
    return Response(
        content=translated_message,
        status_code=status_code,
        headers=headers,
        media_type="text/plain",
    )


def create_response(
    data: Optional[Any] = None,
    message_key: Optional[str] = None,
    message_placeholders: Optional[Dict[str, str]] = None,
    status_code: int = status.HTTP_200_OK,
    response_model: Optional[Type[BaseResponseModel]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Union[Response, Dict[str, Any]]:
    """
    Create a response with the given data and message.

    Args:
        data: Optional data to include in the response
        message_key: Optional message key for translation
        message_placeholders: Optional placeholders for the message
        status_code: The HTTP status code to return
        response_model: Optional response model to use
        headers: Optional headers to include in the response

    Returns:
        A response object or dictionary
    """
    # Get the current request language
    language = get_request_language()

    # Create response message if a key is provided
    if message_key:
        response_message = ResponseMessage(message_key, message_placeholders)
        translated_message = response_message.translate(language.value)
    else:
        translated_message = ""

    # If no response model is specified
    if not response_model:
        if data is not None:
            # Return data directly if no model is specified
            return cast(Dict[str, Any], data)
        elif message_key:
            # Return a simple text response with the translated message
            return Response(
                content=translated_message,
                status_code=status_code,
                headers=headers,
                media_type="text/plain",
            )
        else:
            # Return an empty response
            return Response(status_code=status_code, headers=headers)

    # If a response model is specified
    if issubclass(response_model, DataResponseModel):
        # Create a data response
        response_data = response_model(
            code=ResponseCode.SUCCESS,
            message=translated_message,
            data=data,
        )
        return cast(Dict[str, Any], response_data)
    elif issubclass(response_model, ErrorResponseModel):
        # Create an error response
        error_response = response_model(
            code=ResponseCode.ERROR,
            message=translated_message,
            details=data,
        )
        return cast(Dict[str, Any], error_response)
    else:
        # Create a base response
        base_response = response_model(
            code=ResponseCode.SUCCESS if status_code < 400 else ResponseCode.ERROR,
            message=translated_message,
        )
        return cast(Dict[str, Any], base_response)

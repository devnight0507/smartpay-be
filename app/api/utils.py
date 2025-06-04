"""
API utility functions.
"""

import re
from typing import Any, Dict, Optional, Type, TypeVar, Union, cast

import dns.resolver
from fastapi import Response, status

from app.api.middleware import get_request_language
from app.api.responses import (
    BaseResponseModel,
    DataResponseModel,
    ErrorResponseModel,
    ResponseCode,
    ResponseMessage,
)
from app.schemas.schemas import CardValidation

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
        response_data = response_model(  # type: ignore
            code=ResponseCode.SUCCESS,
            message=translated_message,
            data=data,
        )
        return cast(Dict[str, Any], response_data)
    elif issubclass(response_model, ErrorResponseModel):
        # Create an error response
        error_response = response_model(
            detail=data,
        )
        return cast(Any, error_response)
    else:
        # Create a base response
        base_response = response_model(  # type: ignore
            code=ResponseCode.SUCCESS if status_code < 400 else ResponseCode.ERROR,
            message=translated_message,
        )
        return cast(Dict[str, Any], base_response)


EMAIL_REGEX = re.compile(r"^[^@]+@([^@]+\.[^@]+)$")


def is_valid_email_dns(email: str) -> bool:
    match = EMAIL_REGEX.match(email)
    if not match:
        return False

    domain = match.group(1)

    try:
        # Check for MX records
        answers = dns.resolver.resolve(domain, "MX")
        return len(answers) > 0
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
        return False


def luhn_checksum(card_number: str) -> bool:
    """Check if card number passes the Luhn algorithm."""
    digits = [int(d) for d in card_number if d.isdigit()]
    checksum = 0

    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit

    return checksum % 10 == 0


def get_card_type(card_number: str) -> str:
    """Return the type of card (Visa, MasterCard, etc.) based on IIN range."""
    if re.match(r"^4[0-9]{12}(?:[0-9]{3})?$", card_number):
        return "Visa"
    elif re.match(r"^5[1-5][0-9]{14}$", card_number):
        return "MasterCard"
    elif re.match(r"^3[47][0-9]{13}$", card_number):
        return "American Express"
    elif re.match(r"^6(?:011|5[0-9]{2})[0-9]{12}$", card_number):
        return "Discover"
    else:
        return "Unknown"


def is_valid_card(card_number: str) -> CardValidation:
    card_number = card_number.replace(" ", "").replace("-", "")
    is_valid = card_number.isdigit() and luhn_checksum(card_number)
    return CardValidation(valid=is_valid, card_type=get_card_type(card_number), length=len(card_number))

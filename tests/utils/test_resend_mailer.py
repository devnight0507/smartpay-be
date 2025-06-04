from unittest import mock

import pytest

from app.core.config import settings
from app.utils.resend_mailer import send_verification_code


@pytest.mark.asyncio
async def test_send_verification_code_prod_mode():
    # Set the settings to simulate the production mode
    settings.MAIL_MODE = "prod"
    settings.RESEND_API_KEY = "dummy_api_key"
    settings.RESEND_DOMAIN = "smartpay.com"

    # Mock the `resend.Emails.send` method to return a mock response
    with mock.patch("resend.Emails.send", return_value={"status": "sent", "to": "test@example.com"}):
        response = await send_verification_code("test@example.com", "123456")

    # Check the response
    assert response == {"status": "sent", "to": "test@example.com"}

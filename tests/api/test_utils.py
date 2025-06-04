import pytest
from fastapi import Response

from app.api import utils
from app.api.responses import (
    BaseResponseModel,
    DataResponseModel,
    ErrorResponseModel,
    ResponseCode,
    ResponseMessage,
)
from app.schemas.schemas import CardValidation


# --- Mocking language and translation ---
class MockLanguage:
    value = "en"


class MockResponseMessage(ResponseMessage):
    def translate(self, lang: str) -> str:
        return f"translated-{self.key}"


@pytest.fixture(autouse=True)
def patch_get_request_language(monkeypatch):
    monkeypatch.setattr("app.api.utils.get_request_language", lambda: MockLanguage())


@pytest.fixture(autouse=True)
def patch_response_message(monkeypatch):
    class MockResponseMessage:
        def __init__(self, key, placeholders=None):
            self.key = key
            self.placeholders = placeholders

        def translate(self, lang: str) -> str:
            return f"translated-{self.key}"

    monkeypatch.setattr("app.api.utils.ResponseMessage", MockResponseMessage)


# --- translate_response_message ---
def test_translate_response_message():
    msg = ResponseMessage("greeting")
    response = utils.translate_response_message(msg, status_code=201, headers={"X-Test": "yes"})
    assert isinstance(response, Response)
    assert response.status_code == 201
    assert response.body == b"greeting"
    assert response.headers["X-Test"] == "yes"


# --- create_response ---
def test_create_response_plain_text():
    response = utils.create_response(message_key="hello", status_code=202)
    assert isinstance(response, Response)
    assert response.status_code == 202
    assert response.body == b"translated-hello"


def test_create_response_empty():
    response = utils.create_response()
    assert isinstance(response, Response)
    assert response.status_code == 200
    assert response.body == b""


def test_create_response_raw_data():
    data = {"x": 123}
    result = utils.create_response(data=data)
    assert result == data


def test_create_response_with_data_model():
    result = utils.create_response(
        data={"foo": "bar"},
        message_key="data-ok",
        response_model=DataResponseModel,
    )
    result_dict = result.dict()
    assert result_dict["code"] == ResponseCode.SUCCESS
    assert result_dict["message"] == "translated-data-ok"
    assert result_dict["data"] == {"foo": "bar"}


def test_create_response_with_error_model():
    result = utils.create_response(
        data="error detail",
        message_key="error-occurred",
        response_model=ErrorResponseModel,
    )
    result_dict = result.dict()
    assert result_dict["detail"] == "error detail"


class CustomBaseResponse(BaseResponseModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


def test_create_response_with_base_model_success():
    result = utils.create_response(message_key="base-success", response_model=CustomBaseResponse, status_code=200)
    result_dict = result.dict()
    assert result_dict["code"] == ResponseCode.SUCCESS
    assert result_dict["message"] == "translated-base-success"


def test_create_response_with_base_model_error():
    result = utils.create_response(message_key="base-error", response_model=CustomBaseResponse, status_code=400)
    result_dict = result.dict()
    assert result_dict["code"] == ResponseCode.ERROR
    assert result_dict["message"] == "translated-base-error"


# --- DNS Email Validation ---
def test_is_valid_email_dns_valid(monkeypatch):
    def mock_resolve(domain, record_type):
        class Answer:
            def __len__(self):
                return 1

        return Answer()

    monkeypatch.setattr("dns.resolver.resolve", mock_resolve)
    assert utils.is_valid_email_dns("test@example.com") is True


def test_is_valid_email_dns_invalid_format():
    assert utils.is_valid_email_dns("invalid-email") is False


# def test_is_valid_email_dns_invalid_dns(monkeypatch):
#     def mock_resolve(domain, record_type):
#         raise dns.resolver.NoAnswer()

#     monkeypatch.setattr("dns.resolver.resolve", mock_resolve)
#     assert utils.is_valid_email_dns("test@noanswer.com") is False


# --- Card Validation ---
def test_luhn_checksum_valid():
    assert utils.luhn_checksum("4539578763621486") is True


def test_luhn_checksum_invalid():
    assert utils.luhn_checksum("1234567890123456") is False


def test_get_card_type_visa():
    assert utils.get_card_type("4111111111111111") == "Visa"


def test_get_card_type_mastercard():
    assert utils.get_card_type("5105105105105100") == "MasterCard"


def test_get_card_type_amex():
    assert utils.get_card_type("378282246310005") == "American Express"


def test_get_card_type_discover():
    assert utils.get_card_type("6011111111111117") == "Discover"


def test_get_card_type_unknown():
    assert utils.get_card_type("7777777777777777") == "Unknown"


def test_is_valid_card_valid():
    result: CardValidation = utils.is_valid_card("4111 1111 1111 1111")
    assert result.valid is True
    assert result.card_type == "Visa"
    assert result.length == 16


def test_is_valid_card_invalid():
    result: CardValidation = utils.is_valid_card("1234 5678 9012 3456")
    assert result.valid is False
    assert result.card_type == "Unknown"
    assert result.length == 16

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


# --- create_response with no model ---
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
    assert result == data  # raw data returned


# --- create_response with DataResponseModel ---
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


# --- create_response with ErrorResponseModel ---
def test_create_response_with_error_model():
    result = utils.create_response(
        data={"error": "details"},
        message_key="error-occurred",
        response_model=ErrorResponseModel,
    )
    result_dict = result.dict()
    assert result_dict["code"] == ResponseCode.ERROR
    assert result_dict["message"] == "translated-error-occurred"
    assert result_dict["details"] == {"error": "details"}


# --- create_response with BaseResponseModel ---
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

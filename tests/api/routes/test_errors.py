import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.errors import create_error_response, register_exception_handlers


@pytest.fixture(scope="module")
def app_with_errors():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/validation")
    async def validation_endpoint(param: int):
        return {"param": param}

    @app.get("/integrity")
    async def integrity_error():
        raise IntegrityError("mock stmt", "mock params", "mock orig")

    @app.get("/sqlalchemy")
    async def sqlalchemy_error():
        raise SQLAlchemyError("mock SQL error")

    @app.get("/general")
    async def general_error():
        raise Exception("some unexpected error")

    return app


@pytest.mark.anyio
async def test_validation_exception(app_with_errors):
    async with AsyncClient(app=app_with_errors, base_url="http://test") as ac:
        response = await ac.get("/validation", params={"param": "abc"})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert "param" in response.json()["error"]["details"]["errors"]


@pytest.mark.anyio
async def test_integrity_exception(app_with_errors):
    async with AsyncClient(app=app_with_errors, base_url="http://test") as ac:
        response = await ac.get("/integrity")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "DATABASE_INTEGRITY_ERROR"
        assert "constraint" in response.json()["error"]["message"].lower()


@pytest.mark.anyio
async def test_sqlalchemy_exception(app_with_errors):
    async with AsyncClient(app=app_with_errors, base_url="http://test") as ac:
        response = await ac.get("/sqlalchemy")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "DATABASE_ERROR"
        assert "database" in response.json()["error"]["message"].lower()


def test_create_error_response():
    result = create_error_response("CUSTOM_CODE", "Custom error occurred", {"field": "value"})
    assert result == {
        "error": {
            "code": "CUSTOM_CODE",
            "message": "Custom error occurred",
            "details": {"field": "value"},
        }
    }

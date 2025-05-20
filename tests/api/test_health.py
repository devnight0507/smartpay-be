"""
Tests for health check endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def test_basic_health_check(client: AsyncClient) -> None:
    """
    Test the basic health check endpoint.
    """
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert "status" in response.json()
    assert response.json()["status"] == "ok"
    assert "version" in response.json()
    assert "environment" in response.json()


async def test_readiness_check(client: AsyncClient, db_session: AsyncSession) -> None:
    """
    Test the readiness check endpoint.
    """
    response = await client.get("/api/health/ready")

    # Since we mocked the dependencies, we expect a 200 response
    # In a real test with actual dependencies, this could return 503 if services are unhealthy
    assert response.status_code == 200

    # Check response structure
    data = response.json()
    assert "status" in data
    assert "components" in data

    # Check components
    components = {c["name"]: c["status"] for c in data["components"]}

    # Since we're using test mocks, we can customize the assertion based on
    # our test environment. In a real test with actual service connections,
    # you would check for actual health.
    assert "database" in components

"""Tests for health endpoints."""

import pytest
from httpx import AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test basic health check."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "govsniper"


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "GovSniper"
    assert data["version"] == "1.0.0"

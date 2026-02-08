"""Smoke tests for the FastAPI application."""

import pytest
from httpx import ASGITransport, AsyncClient

from analyzer.main import create_app


@pytest.fixture
def app():
    """Create a fresh app instance for testing.

    Note: ASGITransport does not invoke the lifespan handler,
    so Firebase Admin SDK initialization is not triggered.
    """
    return create_app()


@pytest.fixture
async def client(app):
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthCheck:
    """Tests for the health check endpoint."""

    async def test_health_returns_200(self, client):
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_health_returns_healthy_status(self, client):
        response = await client.get("/health")
        assert response.json() == {"status": "healthy"}


class TestAppRouting:
    """Tests that app routes are correctly mounted."""

    async def test_api_router_is_mounted(self, client):
        """Authenticated endpoints return 401/403 without a token,
        which proves the route exists and the router is mounted."""
        response = await client.get("/api/documents")
        assert response.status_code in (401, 403)

    async def test_unknown_route_returns_404(self, client):
        response = await client.get("/nonexistent")
        assert response.status_code == 404

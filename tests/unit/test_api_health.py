"""
API Tests – Health Endpoints

Tests that health check routes return expected responses.
No LLM or database required.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestHealthEndpoints:
    """Tests for /health and /health/ready endpoints."""

    def test_liveness_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_liveness_response_structure(self, client):
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "env" in data
        assert "checks" in data
        assert data["status"] == "ok"

    def test_liveness_api_check_passes(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["checks"]["api"] == "ok"

    def test_readiness_returns_non_500(self, client):
        # Without a real DB the readiness check will return degraded status
        # but should not return a 500 error
        response = client.get("/health/ready")
        assert response.status_code in (200, 503)

    def test_openapi_schema_accessible(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "paths" in schema
        assert "/health" in schema["paths"]
        assert "/api/v1/loans/analyze" in schema["paths"]

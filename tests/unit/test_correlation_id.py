"""
Unit Tests – Correlation ID Middleware

Tests for request correlation and tracing headers.
"""

from fastapi.testclient import TestClient

from app.main import app


class TestCorrelationIDMiddleware:
    """Test correlation ID middleware functionality."""

    def test_correlation_id_generated(self) -> None:
        """Test that correlation ID is generated if not provided."""
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert "X-Correlation-ID" in response.headers
            assert len(response.headers["X-Correlation-ID"]) > 0

    def test_request_id_generated(self) -> None:
        """Test that request ID is always generated."""
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert "X-Request-ID" in response.headers
            assert len(response.headers["X-Request-ID"]) > 0

    def test_correlation_id_propagated(self) -> None:
        """Test that provided correlation ID is propagated."""
        with TestClient(app) as client:
            provided_correlation_id = "test-correlation-123"
            response = client.get(
                "/health",
                headers={"X-Correlation-ID": provided_correlation_id},
            )
            assert response.status_code == 200
            assert response.headers["X-Correlation-ID"] == provided_correlation_id

    def test_unique_request_ids(self) -> None:
        """Test that each request gets a unique request ID."""
        with TestClient(app) as client:
            response1 = client.get("/health")
            response2 = client.get("/health")
            assert response1.headers["X-Request-ID"] != response2.headers["X-Request-ID"]

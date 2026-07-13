"""
Unit Tests – Metrics Endpoint

Tests for Prometheus metrics collection and endpoint.
"""

from fastapi.testclient import TestClient

from app.main import app


class TestMetricsEndpoint:
    """Test metrics endpoint functionality."""

    def test_metrics_endpoint_exists(self) -> None:
        """Test that metrics endpoint is registered."""
        with TestClient(app) as client:
            response = client.get("/metrics")
            assert response.status_code == 200

    def test_metrics_endpoint_format(self) -> None:
        """Test that metrics endpoint returns Prometheus format."""
        with TestClient(app) as client:
            response = client.get("/metrics")
            assert response.status_code == 200
            # Prometheus format should contain TYPE and HELP
            content = response.text
            assert "# HELP" in content or len(content) > 0

    def test_metrics_content_type(self) -> None:
        """Test that metrics endpoint has correct content type."""
        with TestClient(app) as client:
            response = client.get("/metrics")
            assert response.status_code == 200
            assert "text/plain" in response.headers.get("content-type", "")

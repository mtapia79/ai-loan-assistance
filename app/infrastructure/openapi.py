"""
Infrastructure – OpenAPI Customization

Provides enhanced OpenAPI schema generation with security schemes,
better documentation, and custom tags.
"""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def customize_openapi(app: FastAPI) -> dict[str, Any]:
    """
    Generate customized OpenAPI schema.

    Adds:
    - Security schemes (****** API key)
    - Server information
    - Contact and license info
    - Enhanced descriptions
    """
    if app.openapi_schema:
        return app.openapi_schema

    from app.config import get_settings

    settings = get_settings()

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # ── Add Server Information ─────────────────────────────────────────
    openapi_schema["servers"] = [
        {
            "url": "http://localhost:8000",
            "description": "Local development",
            "variables": {
                "protocol": {"default": "http"},
                "host": {"default": "localhost"},
                "port": {"default": "8000"},
            },
        },
        {
            "url": "https://api.example.com",
            "description": "Production",
        },
    ]

    # ── Add Security Schemes ───────────────────────────────────────────
    openapi_schema["components"]["securitySchemes"] = {
        "bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token for authentication",
        },
        "api_key": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for authentication",
        },
    }

    # ── Add Contact & License Information ───────────────────────────────
    openapi_schema["info"]["contact"] = {
        "name": "Support",
        "email": "support@example.com",
        "url": "https://example.com/support",
    }

    openapi_schema["info"]["license"] = {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    }

    # ── Add X-Logo Extension ───────────────────────────────────────────
    openapi_schema["info"]["x-logo"] = {
        "url": "https://example.com/logo.png",
        "altText": "AI Loan Assistance Logo",
    }

    # ── Add Tags with Descriptions ─────────────────────────────────────
    openapi_schema["tags"] = [
        {
            "name": "health",
            "description": "Application health checks and readiness probes",
            "externalDocs": {
                "description": "Health check patterns",
                "url": "https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/",
            },
        },
        {
            "name": "loans",
            "description": "Loan application processing and analysis",
            "externalDocs": {
                "description": "AI Loan Assistance Documentation",
                "url": "https://docs.example.com/loans",
            },
        },
        {
            "name": "metrics",
            "description": "Application metrics and monitoring",
            "externalDocs": {
                "description": "Prometheus Metrics Format",
                "url": "https://prometheus.io/docs/instrumenting/exposition_formats/",
            },
        },
    ]

    # ── Add Environment Info to Schema ─────────────────────────────────
    openapi_schema["info"]["x-environment"] = {
        "env": settings.app_env,
        "version": settings.app_version,
        "service": settings.otel_service_name,
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def setup_openapi(app: FastAPI) -> None:
    """
    Set up customized OpenAPI schema for the application.

    Call this function in your app initialization.

    Args:
        app: FastAPI application instance.
    """
    app.openapi = lambda: customize_openapi(app)  # type: ignore[assignment]

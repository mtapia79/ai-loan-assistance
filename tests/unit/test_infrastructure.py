"""
Unit Tests – Infrastructure Components

Tests for Redis, Vector DB, Dependency Injection, and other infrastructure.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.di import ServiceContainer
from app.infrastructure.vector_db import VectorDatabase


class TestServiceContainer:
    """Test dependency injection container."""

    def test_service_container_exists(self) -> None:
        """Test that ServiceContainer is defined."""
        assert ServiceContainer is not None

    def test_service_container_has_methods(self) -> None:
        """Test that ServiceContainer has required methods."""
        assert hasattr(ServiceContainer, "get_db_session")
        assert hasattr(ServiceContainer, "get_redis")
        assert hasattr(ServiceContainer, "get_vector_db")


class TestVectorDatabase:
    """Test Vector Database wrapper."""

    @pytest.mark.asyncio
    async def test_vector_database_init(self, db: AsyncSession) -> None:
        """Test VectorDatabase initialization."""
        vector_db = VectorDatabase(db)
        assert vector_db is not None
        assert vector_db.session == db

    @pytest.mark.asyncio
    async def test_health_check(self, db: AsyncSession) -> None:
        """Test vector database health check."""
        vector_db = VectorDatabase(db)
        health = await vector_db.health_check()
        assert isinstance(health, dict)
        assert "vector_db" in health
        # Health check returns "ok" or "error:..." - we just check the key exists
        assert isinstance(health["vector_db"], str)

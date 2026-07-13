"""
Infrastructure – Dependency Injection Container

Provides a structured way to manage application dependencies
and inject them into handlers/services.
"""

from typing import Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.infrastructure.redis import get_redis_client
from app.infrastructure.vector_db import VectorDatabase
from app.observability.logging import get_logger

logger = get_logger(__name__)


class ServiceContainer:
    """
    Central dependency container for application services.

    This class provides factory methods for common dependencies
    and manages their lifecycle.
    """

    @staticmethod
    async def get_db_session() -> AsyncSession:
        """
        Get a database session.

        This is a FastAPI-compatible dependency.
        """
        async with get_session() as session:
            yield session

    @staticmethod
    async def get_redis() -> Any:  # redis_client.Redis
        """
        Get Redis client.

        This is a FastAPI-compatible dependency.
        """
        return await get_redis_client()

    @staticmethod
    async def get_vector_db(db: AsyncSession = Depends(get_session)) -> VectorDatabase:
        """
        Get vector database wrapper.

        This is a FastAPI-compatible dependency that provides
        a VectorDatabase instance for vector operations.
        """
        return VectorDatabase(db)


# ── FastAPI Dependencies ───────────────────────────────────────────────────

# These can be used directly in route handlers:
# async def my_handler(
#     db: AsyncSession = Depends(get_db_session),
#     redis: redis.Redis = Depends(get_redis),
#     vector_db: VectorDatabase = Depends(get_vector_db),
# ) -> dict:
#     ...


def get_db_service() -> Any:
    """
    Factory for database session dependency.

    Usage:
        async def handler(db = Depends(get_db_service)):
            ...
    """
    return Depends(get_session)


def get_redis_service() -> Any:
    """
    Factory for Redis client dependency.

    Usage:
        async def handler(redis = Depends(get_redis_service)):
            ...
    """
    return Depends(get_redis_client)


def get_vector_db_service() -> Any:
    """
    Factory for vector database dependency.

    Usage:
        async def handler(vector_db = Depends(get_vector_db_service)):
            ...
    """
    return Depends(ServiceContainer.get_vector_db)

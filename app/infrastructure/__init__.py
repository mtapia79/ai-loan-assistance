"""
Infrastructure – Central Management Module

Orchestrates initialization and lifecycle management of all
infrastructure components including databases, cache, and services.
"""

from typing import Any

from app.infrastructure.redis import close_redis, health_check_redis, init_redis
from app.infrastructure.vector_db import VectorDatabase
from app.observability.logging import get_logger

logger = get_logger(__name__)


class InfrastructureManager:
    """
    Central manager for infrastructure components.

    Handles initialization, health checks, and graceful shutdown
    of all infrastructure services with graceful degradation.
    """

    _initialized = False

    @classmethod
    async def initialize(cls) -> None:
        """
        Initialize all infrastructure components.

        Call this in your application startup handler.
        Handles errors gracefully - non-production environments
        continue even if some services fail.
        """
        if cls._initialized:
            logger.warning("infrastructure_already_initialized")
            return

        try:
            logger.info("infrastructure_initialization_start")

            # Initialize Redis (with graceful fallback)
            await init_redis()

            # Database is initialized separately in app/db/session.py::init_db()

            cls._initialized = True
            logger.info("infrastructure_initialization_complete")
        except Exception as exc:
            logger.error("infrastructure_initialization_failed", error=str(exc))
            # Don't re-raise - allow graceful degradation

    @classmethod
    async def shutdown(cls) -> None:
        """
        Gracefully shutdown all infrastructure components.

        Call this in your application shutdown handler.
        """
        try:
            logger.info("infrastructure_shutdown_start")

            # Shutdown Redis
            await close_redis()

            cls._initialized = False
            logger.info("infrastructure_shutdown_complete")
        except Exception as exc:
            logger.error("infrastructure_shutdown_error", error=str(exc))
            # Don't raise on shutdown to allow graceful termination

    @classmethod
    async def health_check(cls) -> dict[str, Any]:
        """
        Perform health checks on all infrastructure components.

        Returns:
            Dict with health status of each component.
            Example: {"redis": "ok", "database": "ok", "vector_db": "ok"}
        """
        health = {}

        # Check Redis
        redis_health = await health_check_redis()
        health.update(redis_health)

        # Check Database (via health module)
        try:
            from app.db.session import get_session

            async for session in get_session():
                from sqlalchemy import text

                await session.execute(text("SELECT 1"))
                health["database"] = "ok"
                break
        except Exception as exc:
            health["database"] = f"error: {exc}"

        # Overall status
        all_ok = all(v == "ok" for v in health.values())
        health["overall"] = "ok" if all_ok else "degraded"

        return health


# ── Public API ──────────────────────────────────────────────────────────────

__all__ = [
    "InfrastructureManager",
    "VectorDatabase",
]

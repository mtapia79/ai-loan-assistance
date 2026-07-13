"""
Infrastructure – Redis Connection Manager

Provides async Redis client with connection pooling, health checks,
and graceful lifecycle management.
"""

import redis.asyncio as redis_client
from redis.asyncio.connection import ConnectionPool

from app.observability.logging import get_logger

logger = get_logger(__name__)

_redis_client: redis_client.Redis | None = None
_redis_initialized = False


async def get_redis_client() -> redis_client.Redis:
    """Get or create the global Redis client."""
    global _redis_client
    if _redis_client is None:
        raise RuntimeError("Redis not initialized – call init_redis() first")
    return _redis_client


async def init_redis() -> None:
    """Initialize Redis client with connection pooling."""
    global _redis_client, _redis_initialized
    from app.config import get_settings

    settings = get_settings()

    try:
        pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=10,
            socket_connect_timeout=5,
            socket_keepalive=True,
            socket_keepalive_options={
                1: 1,  # TCP_KEEPIDLE
                2: 1,  # TCP_KEEPINTVL
                3: 3,  # TCP_KEEPCNT
            },
        )
        _redis_client = redis_client.Redis(connection_pool=pool)

        # Verify connection with short timeout
        try:
            await _redis_client.ping()
            _redis_initialized = True
            logger.info("redis_initialized", host=settings.redis_host, port=settings.redis_port)
        except Exception as ping_exc:
            logger.warning(
                "redis_ping_failed",
                error=str(ping_exc),
                host=settings.redis_host,
                port=settings.redis_port,
            )
            # In non-production, allow graceful degradation
            if settings.app_env == "production":
                raise
            _redis_initialized = False
            _redis_client = None
    except Exception as exc:
        logger.warning(
            "redis_initialization_warning",
            error=str(exc),
            env=settings.app_env,
        )
        # Allow app to continue without Redis in non-production
        if settings.app_env == "production":
            raise
        _redis_client = None


async def close_redis() -> None:
    """Close Redis client and connection pool."""
    global _redis_client, _redis_initialized
    if _redis_client is not None:
        try:
            await _redis_client.close()
            logger.info("redis_closed")
        except Exception as exc:
            logger.warning("redis_close_error", error=str(exc))
        finally:
            _redis_client = None
            _redis_initialized = False


async def health_check_redis() -> dict[str, str]:
    """
    Check Redis health.

    Returns:
        dict with status "ok" or error message.
    """
    if not _redis_initialized:
        return {"redis": "unavailable"}

    try:
        client = await get_redis_client()
        response = await client.ping()
        if response:
            return {"redis": "ok"}
        return {"redis": "error: ping failed"}
    except Exception as exc:
        return {"redis": f"error: {exc}"}

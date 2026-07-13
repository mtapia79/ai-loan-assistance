"""
Database – SQLAlchemy Async Session Factory

Provides a lifespan-managed async engine and a dependency-injectable
session for use within FastAPI route handlers.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.observability.logging import get_logger

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    from app.config import get_settings

    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.app_env == "development",
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )


def init_db() -> None:
    """Create engine and session factory (call once at startup)."""
    global _engine, _session_factory
    _engine = get_engine()
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    logger.info("database_pool_created")


async def close_db() -> None:
    """Dispose the engine (call at shutdown)."""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("database_pool_closed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session per request.

    Usage::

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_session)):
            ...
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialised – call init_db() first")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_context() -> AsyncGenerator[AsyncSession, None]:
    """Context-manager variant for use outside of FastAPI (e.g. scripts)."""
    if _session_factory is None:
        init_db()
    session_factory = _session_factory
    if session_factory is None:
        raise RuntimeError("Database not initialised – call init_db() first")
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

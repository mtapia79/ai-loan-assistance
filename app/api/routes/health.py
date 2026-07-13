"""
API Routes – Health Check

Provides liveness and readiness probes for Kubernetes.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_session
from app.schemas.loan import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe – always returns 200 if the process is alive."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        env=settings.app_env,
        checks={"api": "ok"},
    )


@router.get("/health/ready", response_model=HealthResponse)
async def readiness_check(db: AsyncSession = Depends(get_session)) -> HealthResponse:
    """
    Readiness probe – checks that the database is reachable.

    Returns 200 when ready to serve traffic, 503 otherwise.
    """
    settings = get_settings()
    checks: dict[str, str] = {"api": "ok"}

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"

    return HealthResponse(
        status=status,
        version=settings.app_version,
        env=settings.app_env,
        checks=checks,
    )

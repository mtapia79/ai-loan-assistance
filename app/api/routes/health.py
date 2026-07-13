"""
API Routes – Health Check

Provides liveness and readiness probes for Kubernetes and load balancers.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_session
from app.infrastructure import InfrastructureManager
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
    Readiness probe – checks that critical dependencies are available.

    Returns 200 when ready to serve traffic, 503 otherwise.
    Checks:
    - Database connectivity
    - Redis connectivity
    - All core infrastructure services
    """
    settings = get_settings()
    checks: dict[str, str] = {"api": "ok"}

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"

    # Check infrastructure (Redis, etc.)
    try:
        infra_health = await InfrastructureManager.health_check()
        checks.update(infra_health)
    except Exception as exc:  # noqa: BLE001
        checks["infrastructure"] = f"error: {exc}"

    # Overall status: 200 if all ok, 503 if any error
    status_str = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    status_code = (
        status.HTTP_200_OK if status_str == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    response = HealthResponse(
        status=status_str,
        version=settings.app_version,
        env=settings.app_env,
        checks=checks,
    )

    # If degraded, raise exception to set proper HTTP status code
    if status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
        raise HTTPException(
            status_code=status_code,
            detail=f"Service degraded. Checks: {checks}",
        )

    return response

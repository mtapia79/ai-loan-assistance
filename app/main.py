"""
AI Loan Assistance – FastAPI Application Entry Point

Architecture highlights demonstrated:
  ✓ FastAPI + async request handling
  ✓ LangGraph multi-agent orchestration (see app/agents/orchestrator.py)
  ✓ MCP tool definitions (see app/mcp/tools.py)
  ✓ RAG with pgvector (see app/rag/)
  ✓ PostgreSQL + SQLAlchemy async (see app/db/)
  ✓ OpenTelemetry tracing (see app/observability/telemetry.py)
  ✓ Structured JSON logging (see app/observability/logging.py)
  ✓ Guardrails – input + output validation (see app/guardrails/validators.py)
  ✓ Evaluation framework (see app/evaluation/evaluator.py)
  ✓ Explainability – agent step trace in every response
  ✓ Docker + Kubernetes ready (see docker-compose.yml + k8s/)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware.correlation import CorrelationIDMiddleware
from app.api.routes import health, loans, metrics
from app.config import get_settings
from app.db.session import close_db, init_db
from app.infrastructure import InfrastructureManager
from app.infrastructure.openapi import setup_openapi
from app.observability.logging import configure_logging, get_logger
from app.observability.telemetry import setup_telemetry

settings = get_settings()

# Configure logging before anything else
configure_logging(settings.log_level)
logger = get_logger(__name__)


# ── Application Lifespan ───────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown resources."""
    logger.info("app_startup", env=settings.app_env, version=settings.app_version)

    # Initialize core databases
    init_db()

    # Initialize infrastructure services (Redis, etc.)
    await InfrastructureManager.initialize()

    # Re-run telemetry setup to configure exporters at runtime
    # (FastAPI app instrumentation was already done at module level)
    setup_telemetry()

    logger.info("app_startup_complete")
    yield
    logger.info("app_shutdown")

    # Graceful shutdown
    await InfrastructureManager.shutdown()
    await close_db()


# ── FastAPI Instance ───────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Enterprise AI Loan Decision Assistant – "
        "Multi-agent RAG system for explainable loan recommendations."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Set up customized OpenAPI schema
setup_openapi(app)

# ── Middleware ─────────────────────────────────────────────────────────────────

# Correlation ID middleware (must be before CORS)
app.add_middleware(CorrelationIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Observability ──────────────────────────────────────────────────────────────
# Instrument the FastAPI app with OpenTelemetry at module level, BEFORE the
# middleware stack is built. Calling instrument_app inside the lifespan is too
# late – Starlette builds middleware_stack on the very first ASGI call (the
# lifespan startup event itself), so add_middleware would raise RuntimeError.
setup_telemetry(app)

# ── Exception Handlers ─────────────────────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(loans.router)
app.include_router(metrics.router)

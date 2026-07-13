"""
API Routes – Metrics and Monitoring

Provides Prometheus-compatible metrics endpoint for monitoring
application health and performance.
"""

from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, generate_latest

from app.config import get_settings
from app.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["metrics"])

# ── Prometheus Metrics ─────────────────────────────────────────────────────

# Request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Application metrics
loan_analysis_total = Counter(
    "loan_analysis_total",
    "Total loan analyses",
    ["recommendation", "status"],
)

loan_analysis_duration_seconds = Histogram(
    "loan_analysis_duration_seconds",
    "Loan analysis duration in seconds",
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

# Database metrics
database_query_duration_seconds = Histogram(
    "database_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0),
)

database_errors_total = Counter(
    "database_errors_total",
    "Total database errors",
    ["operation", "error_type"],
)

# Cache metrics
cache_hits_total = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["cache_type"],
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["cache_type"],
)

# Vector DB metrics
vector_db_operations_total = Counter(
    "vector_db_operations_total",
    "Total vector database operations",
    ["operation", "status"],
)


@router.get(
    "/metrics",
    response_class=Response,
    tags=["metrics"],
    summary="Prometheus Metrics",
    description="Prometheus-format metrics endpoint for monitoring",
)
async def metrics() -> Response:
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format.
    Can be scraped by Prometheus or other monitoring systems.

    Response format: text/plain

    Example metrics:
    - http_requests_total: Total HTTP requests by method, endpoint, status
    - http_request_duration_seconds: Request latency distribution
    - loan_analysis_total: Total loan analyses by recommendation type
    - database_query_duration_seconds: Database query latencies
    - cache_hits_total: Cache hit counts
    """
    settings = get_settings()

    try:
        metrics_data = generate_latest()
        logger.info("metrics_endpoint_called")
        return Response(
            content=metrics_data,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )
    except Exception as exc:
        logger.error("metrics_generation_error", error=str(exc))
        return Response(
            content="# Error generating metrics\n",
            status_code=500,
            media_type="text/plain; charset=utf-8",
        )

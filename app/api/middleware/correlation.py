"""
API Middleware – Correlation IDs

Middleware that assigns request IDs and propagates correlation IDs
throughout the request lifecycle for distributed tracing.
"""

import time
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Extracts or generates X-Correlation-ID from request headers
    2. Generates unique X-Request-ID for this request
    3. Binds both to structlog context for all downstream logs
    4. Includes both in response headers
    5. Tracks request timing and status
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        # Extract or generate correlation ID
        correlation_id = request.headers.get(
            "X-Correlation-ID",
            str(uuid.uuid4()),
        )

        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Track timing
        start_time = time.time()

        # Clear and bind context for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
        )

        logger.info(
            "request_start",
            query_string=request.url.query if request.url.query else None,
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error(
                "request_exception",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "request_complete",
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )

        # Add headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id

        return response

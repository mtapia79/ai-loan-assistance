"""
API Middleware – Request / Response Logging

Logs every HTTP request with timing, status code, and trace correlation.
"""

import time
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Assigns a unique request_id to every request
    2. Binds request_id and path to the structlog context
    3. Logs request start and completion with timing
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = str(uuid.uuid4())
        start_time = time.time()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        logger.info("request_start")

        response = await call_next(request)

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "request_complete",
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )

        response.headers["X-Request-ID"] = request_id
        return response

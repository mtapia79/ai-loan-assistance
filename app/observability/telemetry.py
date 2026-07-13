"""
Observability – OpenTelemetry Tracing

Configures SDK with OTLP export.  When OTEL_ENABLED=false (local dev)
a no-op tracer is used so the rest of the code remains unchanged.
"""

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.observability.logging import get_logger

logger = get_logger(__name__)

_tracer_provider: TracerProvider | None = None


def setup_telemetry(app=None) -> None:  # type: ignore[assignment]
    """
    Initialise OpenTelemetry.

    Args:
        app: Optional FastAPI application to auto-instrument.
    """
    from app.config import get_settings

    settings = get_settings()

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.app_env,
        }
    )

    global _tracer_provider
    _tracer_provider = TracerProvider(resource=resource)

    if settings.otel_enabled:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
            _tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info(
                "otel_configured",
                endpoint=settings.otel_exporter_otlp_endpoint,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("otel_exporter_unavailable", error=str(exc))
            _tracer_provider.add_span_processor(
                BatchSpanProcessor(InMemorySpanExporter())
            )
    else:
        # Use in-memory exporter in dev/test so no real endpoint is needed
        _tracer_provider.add_span_processor(
            BatchSpanProcessor(InMemorySpanExporter())
        )

    trace.set_tracer_provider(_tracer_provider)

    if app is not None:
        FastAPIInstrumentor.instrument_app(app)

    SQLAlchemyInstrumentor().instrument()
    logger.info("telemetry_ready", enabled=settings.otel_enabled)


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer for the given instrumentation scope."""
    return trace.get_tracer(name)

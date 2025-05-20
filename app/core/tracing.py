"""
OpenTelemetry distributed tracing configuration.
"""

from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from fastapi import FastAPI
from loguru import logger
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio
from opentelemetry.trace import Span, SpanKind, Tracer

from app.core.config import settings
from app.db.session import engine


def configure_tracer() -> TracerProvider:
    """
    Configure the OpenTelemetry tracer.

    This sets up the global tracer provider with appropriate sampling,
    processors, and exporters.

    Returns:
        The configured tracer provider
    """
    # Create a resource with service information
    resource = Resource.create(
        {
            "service.name": settings.PROJECT_NAME,
            "service.version": settings.VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    # Create the tracer provider with sampling strategy
    tracer_provider = TracerProvider(
        resource=resource,
        sampler=ParentBasedTraceIdRatio(0.1),  # Sample 10% of traces
    )

    # Use console exporter for development
    if settings.ENVIRONMENT == "development":
        console_processor = BatchSpanProcessor(ConsoleSpanExporter())
        tracer_provider.add_span_processor(console_processor)

    # Add OTLP exporter if configured (e.g., Jaeger or other collector)
    if settings.OTLP_ENDPOINT:
        otlp_exporter = OTLPSpanExporter(endpoint=settings.OTLP_ENDPOINT)
        otlp_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(otlp_processor)

    # Set the global tracer provider
    trace.set_tracer_provider(tracer_provider)

    return tracer_provider


def setup_tracing(app: FastAPI) -> None:
    """
    Set up OpenTelemetry tracing for the FastAPI application.

    This configures instrumentation for FastAPI, SQLAlchemy, logging,
    and HTTP clients.

    Args:
        app: The FastAPI application to instrument
    """
    # Skip if tracing is disabled
    if not settings.ENABLE_TRACING:
        return

    try:
        # Configure the tracer
        tracer_provider = configure_tracer()

        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=tracer_provider,
            excluded_urls="api/health,metrics",  # Exclude health and metrics endpoints
        )

        # Instrument SQLAlchemy
        SQLAlchemyInstrumentor().instrument(
            engine=engine,
            tracer_provider=tracer_provider,
        )

        # Instrument HTTPX for outgoing requests
        HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)

        # Instrument logging
        LoggingInstrumentor().instrument(tracer_provider=tracer_provider)

        logger.info("OpenTelemetry tracing configured successfully")
    except Exception as e:
        logger.error(f"Failed to setup OpenTelemetry tracing: {e}")


# Utility functions for manual tracing


def get_tracer(name: str = "app.default") -> Tracer:
    """
    Get a tracer for creating spans.

    Args:
        name: The name of the tracer

    Returns:
        A tracer instance
    """
    return trace.get_tracer(name)


@contextmanager
def create_span(
    name: str, attributes: Optional[Dict[str, Any]] = None, kind: Optional[SpanKind] = None
) -> Generator[Span, None, None]:
    """
    Create a new span (context manager).

    Example usage:
        with create_span("process_payment", {"amount": payment.amount}) as span:
            # Business logic
            span.add_event("payment_processed")

    Args:
        name: The name of the span
        attributes: Optional attributes to add to the span
        kind: Optional span kind

    Returns:
        A span context manager
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(
        name, attributes=attributes, kind=kind if kind is not None else SpanKind.INTERNAL
    ) as span:
        yield span

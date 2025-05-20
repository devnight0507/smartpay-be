"""
Prometheus metrics configuration.
"""

import time
from typing import Any, Callable, TypeVar, cast

from fastapi import FastAPI, Request, Response
from loguru import logger
from prometheus_client import Counter, Gauge, Histogram, Summary
from prometheus_client.openmetrics.exposition import (
    CONTENT_TYPE_LATEST,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

F = TypeVar("F", bound=Callable[..., Any])

# Define metrics
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests count", ["method", "endpoint", "status_code"])

REQUEST_TIME = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float("inf")),
)

REQUEST_IN_PROGRESS = Gauge("http_requests_in_progress", "Number of HTTP requests in progress", ["method", "endpoint"])

EXCEPTION_COUNT = Counter(
    "http_exceptions_total", "Total HTTP exceptions count", ["method", "endpoint", "exception_type"]
)

DB_QUERY_TIME = Summary("db_query_duration_seconds", "Database query duration in seconds", ["query_type", "table"])

KAFKA_MESSAGES_PRODUCED = Counter("kafka_messages_produced_total", "Total Kafka messages produced", ["topic"])

KAFKA_MESSAGES_CONSUMED = Counter("kafka_messages_consumed_total", "Total Kafka messages consumed", ["topic", "group"])

REDIS_OPERATIONS = Counter("redis_operations_total", "Total Redis operations", ["operation"])

REDIS_OPERATION_TIME = Histogram(
    "redis_operation_duration_seconds",
    "Redis operation duration in seconds",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, float("inf")),
)

# Business metrics example
BUSINESS_EVENTS = Counter("business_events_total", "Total business events", ["event_type"])


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Middleware that collects Prometheus metrics for HTTP requests.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        """
        Process a request and collect metrics.
        """
        method = request.method
        path = request.url.path

        # Skip metrics endpoint in metrics
        if path == "/metrics":
            response = await call_next(request)
            return cast(Response, response)

        # Normalize path for metrics
        # Replace path parameter values with their names to prevent high cardinality
        if path.startswith("/api/v1"):
            path_parts = path.split("/")
            if len(path_parts) > 4 and path_parts[4].isdigit():
                path = f"{'/'.join(path_parts[:4])}/{{id}}"

        # Start time
        start_time = time.time()

        # Track in-progress requests
        REQUEST_IN_PROGRESS.labels(method=method, endpoint=path).inc()

        # Process request
        try:
            response = await call_next(request)
            response_typed = cast(Response, response)

            # Record request metrics
            status_code = response_typed.status_code
            REQUEST_COUNT.labels(method=method, endpoint=path, status_code=status_code).inc()
            REQUEST_TIME.labels(method=method, endpoint=path).observe(time.time() - start_time)

            return response_typed
        except Exception as e:
            # Record exception
            status_code = 500
            exception_type = type(e).__name__
            EXCEPTION_COUNT.labels(method=method, endpoint=path, exception_type=exception_type).inc()
            logger.exception(f"Request failed: {str(e)}")
            raise
        finally:
            # Decrement in-progress requests
            REQUEST_IN_PROGRESS.labels(method=method, endpoint=path).dec()


async def metrics_endpoint(request: Request) -> Response:
    """
    Endpoint for exposing Prometheus metrics.
    """
    from prometheus_client import REGISTRY

    data = generate_latest(REGISTRY)
    return Response(content=data, headers={"Content-Type": CONTENT_TYPE_LATEST})


def setup_metrics(app: FastAPI) -> None:
    """
    Set up Prometheus metrics and middleware for FastAPI application.
    """
    # Add Prometheus middleware
    app.add_middleware(PrometheusMiddleware)

    # Add metrics endpoint
    app.add_route("/metrics", metrics_endpoint)

    logger.info("Prometheus metrics configured")


# Utility functions for business metrics


def record_business_event(event_type: str) -> None:
    """Record a business event metric."""
    BUSINESS_EVENTS.labels(event_type=event_type).inc()


def time_db_query(query_type: str, table: str) -> Callable[[F], F]:
    """Decorator to time database queries."""

    def decorator(func: F) -> F:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            result = await func(*args, **kwargs)
            DB_QUERY_TIME.labels(query_type=query_type, table=table).observe(time.time() - start_time)
            return result

        return cast(F, wrapper)

    return decorator


def time_redis_operation(operation: str) -> Callable[[F], F]:
    """Decorator to time Redis operations."""

    def decorator(func: F) -> F:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                REDIS_OPERATIONS.labels(operation=operation).inc()
                return result
            finally:
                REDIS_OPERATION_TIME.labels(operation=operation).observe(time.time() - start_time)

        return cast(F, wrapper)

    return decorator


def record_kafka_message_produced(topic: str) -> None:
    """Record a Kafka message produced metric."""
    KAFKA_MESSAGES_PRODUCED.labels(topic=topic).inc()


def record_kafka_message_consumed(topic: str, group: str) -> None:
    """Record a Kafka message consumed metric."""
    KAFKA_MESSAGES_CONSUMED.labels(topic=topic, group=group).inc()

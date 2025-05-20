"""
Logging configuration.
"""

import json
import logging
import sys
from typing import Any, Dict, cast

from loguru import logger

from app.core.config import settings


class InterceptHandler(logging.Handler):
    """
    Intercept standard logging messages toward Loguru.
    """

    def __init__(self) -> None:
        import logging

        super().__init__()
        self.logging = logging

    def emit(self, record: Any) -> None:
        logger_opt = logger.opt(depth=6, exception=record.exc_info)
        msg = record.getMessage()
        level: int = record.levelno

        if level >= self.logging.CRITICAL:
            logger_opt.critical(msg)
        elif level >= self.logging.ERROR:
            logger_opt.error(msg)
        elif level >= self.logging.WARNING:
            logger_opt.warning(msg)
        elif level >= self.logging.INFO:
            logger_opt.info(msg)
        else:
            logger_opt.debug(msg)


def serialize_record(record: Dict[str, Any]) -> str:
    """
    Custom serializer for Loguru logs.
    """
    try:
        # Create base subset with required fields
        subset = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "service": settings.PROJECT_NAME,
            "environment": settings.ENVIRONMENT,
        }

        # Add optional fields if they exist
        if "name" in record:
            subset["module"] = record["name"]
        if "function" in record:
            subset["function"] = record["function"]
        if "line" in record:
            subset["line"] = record["line"]

        # Add request trace ID if available
        if "extra" in record and isinstance(record["extra"], dict):
            if "trace_id" in record["extra"]:
                subset["trace_id"] = record["extra"]["trace_id"]
            if "span_id" in record["extra"]:
                subset["span_id"] = record["extra"]["span_id"]

            # Add any other extra fields
            for key, value in record["extra"].items():
                if key not in ("trace_id", "span_id") and not key.startswith("_"):
                    subset[key] = value

        # Add exception info if available
        if "exception" in record and record["exception"]:
            subset["exception"] = record["exception"]

        return json.dumps(subset)
    except Exception as e:
        # Fallback to simple format if JSON serialization fails
        return json.dumps(
            {
                "timestamp": (
                    record.get("time", "unknown_time").isoformat()
                    if hasattr(record.get("time", ""), "isoformat")
                    else str(record.get("time", ""))
                ),
                "level": "ERROR",
                "message": f"Error serializing log: {str(e)}",
                "original_message": str(record.get("message", "")),
                "service": settings.PROJECT_NAME,
                "environment": settings.ENVIRONMENT,
            }
        )


def configure_logging() -> None:
    """
    Configure loguru logger.
    """
    import logging

    # Remove default handlers
    logger.remove()

    # Add stderr handler with appropriate format
    if settings.JSON_LOGS:
        logger.add(
            lambda msg: print(serialize_record(cast(Dict[str, Any], msg.record)), file=sys.stderr),
            level=settings.LOG_LEVEL,
            backtrace=True,
            diagnose=True,
        )
    else:
        logger.add(
            sys.stderr,
            level=settings.LOG_LEVEL,
            format="{time} | {level} | {message} | {extra}",
            backtrace=True,
            diagnose=True,
        )

    # Intercept standard logging
    logging.getLogger().handlers = [InterceptHandler()]

    # Set log levels for various libraries
    for logger_name in ["uvicorn", "uvicorn.error", "fastapi", "sqlalchemy.engine.base"]:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False

    logger.info("Logging configured successfully.")

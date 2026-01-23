"""Structured logging configuration with JSON output."""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.

    Outputs logs in JSON format for easy parsing by log aggregation tools
    like ELK, Splunk, CloudWatch, etc.
    """

    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add location info
        log_data["location"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from LogRecord
        if self.include_extra:
            # Standard extra fields we want to include
            extra_fields = [
                "request_id",
                "user",
                "model",
                "prompt_length",
                "response_time_ms",
                "status_code",
                "method",
                "path",
                "cache_hit",
                "cache_type",
                "incident_id",
            ]

            for field in extra_fields:
                if hasattr(record, field):
                    log_data[field] = getattr(record, field)

            # Also include any custom extras
            if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
                log_data.update(record.extra_data)

        return json.dumps(log_data, default=str)


class RequestContextFilter(logging.Filter):
    """
    Logging filter that adds request context to log records.

    This filter pulls request_id and user from a context variable
    that's set by the request_id middleware.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add request context to log record."""
        from middleware.request_id import get_request_context

        try:
            context = get_request_context()
            record.request_id = context.get("request_id", "-")
            record.user = context.get("user", "-")
        except Exception:
            record.request_id = "-"
            record.user = "-"

        return True


def setup_logging(
    level: str = None,
    json_output: bool = True,
) -> None:
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               Defaults to LOG_LEVEL env var or INFO
        json_output: Whether to output JSON formatted logs (default: True)
    """
    # Determine log level
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()

    numeric_level = getattr(logging, level, logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)

    # Set formatter based on output preference
    if json_output:
        formatter = JSONFormatter()
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s | "
            "request_id=%(request_id)s user=%(user)s"
        )

    console_handler.setFormatter(formatter)

    # Add context filter
    console_handler.addFilter(RequestContextFilter())

    root_logger.addHandler(console_handler)

    # Configure specific loggers
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("qdrant_client").setLevel(logging.WARNING)

    # Ensure our app loggers use the configured level
    logging.getLogger("llmops").setLevel(numeric_level)
    logging.getLogger("config").setLevel(numeric_level)
    logging.getLogger("routers").setLevel(numeric_level)
    logging.getLogger("services").setLevel(numeric_level)
    logging.getLogger("middleware").setLevel(numeric_level)

    logging.info(
        "Logging configured",
        extra={"extra_data": {"level": level, "json_output": json_output}},
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    Convenience function to get loggers with consistent naming.

    Args:
        name: Logger name (e.g., "routers.llm", "services.auth")

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)

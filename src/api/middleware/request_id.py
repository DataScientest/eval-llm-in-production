"""Request ID middleware for request tracing."""

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Context variable for request context (thread-safe)
_request_context: ContextVar[Dict[str, Any]] = ContextVar(
    "request_context", default={"request_id": "-", "user": "-"}
)


def get_request_context() -> Dict[str, Any]:
    """Get the current request context."""
    return _request_context.get()


def set_request_context(context: Dict[str, Any]) -> None:
    """Set the current request context."""
    _request_context.set(context)


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return f"req_{uuid.uuid4().hex[:16]}"


async def request_id_middleware(request: Request, call_next):
    """
    Middleware that generates and propagates request IDs.

    - Generates a unique request ID for each request
    - Stores request context for logging
    - Adds X-Request-ID header to response
    - Logs request start and completion
    """
    # Generate or use existing request ID
    request_id = request.headers.get("X-Request-ID") or generate_request_id()

    # Extract user from token if available (will be set by auth)
    user = "-"

    # Set request context for logging
    context = {
        "request_id": request_id,
        "user": user,
        "method": request.method,
        "path": request.url.path,
        "client_ip": request.client.host if request.client else "-",
    }
    set_request_context(context)

    # Store request_id on request state for easy access
    request.state.request_id = request_id

    start_time = time.time()

    # Log request start
    logger.info(
        "Request started",
        extra={
            "request_id": request_id,
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
                "client_ip": context["client_ip"],
            },
        },
    )

    try:
        # Process request
        response = await call_next(request)

        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000

        # Log request completion
        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "extra_data": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "response_time_ms": round(response_time_ms, 2),
                },
            },
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response

    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000

        logger.error(
            "Request failed",
            extra={
                "request_id": request_id,
                "extra_data": {
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "response_time_ms": round(response_time_ms, 2),
                },
            },
        )
        raise
    finally:
        # Reset context
        set_request_context({"request_id": "-", "user": "-"})

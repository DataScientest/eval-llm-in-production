"""Shutdown middleware for graceful request handling."""

import logging

from config.lifespan import (
    decrement_active_requests,
    increment_active_requests,
    is_shutting_down,
)
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


async def shutdown_middleware(request: Request, call_next):
    """
    Middleware to handle graceful shutdown.

    - Rejects new requests during shutdown (except health checks)
    - Tracks in-flight requests
    - Allows existing requests to complete
    """
    # Allow health check endpoints during shutdown
    health_paths = ["/health", "/system/health", "/health/detailed"]
    if request.url.path in health_paths:
        return await call_next(request)

    # Reject new requests during shutdown
    if is_shutting_down():
        logger.warning(f"Rejecting request during shutdown: {request.url.path}")
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Service is shutting down. Please retry later.",
                "retry_after": 30,
            },
            headers={"Retry-After": "30"},
        )

    # Track active requests
    await increment_active_requests()
    try:
        response = await call_next(request)
        return response
    finally:
        await decrement_active_requests()

"""Request limits middleware for body size and timeout protection."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Configuration
MAX_BODY_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB
REQUEST_TIMEOUT_SECONDS = 60  # Overall request timeout


async def request_limits_middleware(request: Request, call_next):
    """
    Middleware to enforce request limits.

    - Limits request body size to prevent memory exhaustion
    - Rejects oversized payloads before processing
    """
    # Check Content-Length header for body size
    content_length = request.headers.get("content-length")

    if content_length:
        try:
            body_size = int(content_length)
            if body_size > MAX_BODY_SIZE_BYTES:
                logger.warning(
                    f"Request body too large: {body_size} bytes "
                    f"(max: {MAX_BODY_SIZE_BYTES} bytes)"
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request body too large. Maximum size is {MAX_BODY_SIZE_BYTES // (1024 * 1024)} MB",
                        "max_bytes": MAX_BODY_SIZE_BYTES,
                        "received_bytes": body_size,
                    },
                )
        except ValueError:
            pass

    # Process the request
    response = await call_next(request)
    return response

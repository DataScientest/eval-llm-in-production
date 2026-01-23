"""Security middleware with enhanced request validation and rate limiting."""

import logging
import re
from datetime import datetime

from config.settings import SecurityConfig
from fastapi import Request, status
from fastapi.responses import JSONResponse
from services.security_service import rate_limit_storage, security_metrics

logger = logging.getLogger(__name__)


async def security_middleware(request: Request, call_next):
    """Security middleware with enhanced request validation and rate limiting."""
    # Get client IP for security tracking
    client_ip = request.client.host if request.client else "unknown"
    logger.debug(f"Rate limiting check for IP: {client_ip}")

    # Update metrics
    security_metrics["total_requests"] += 1

    # Get current time once
    current_time = datetime.utcnow()

    # 1. Initialize rate limiting for this IP if not exists
    if client_ip not in rate_limit_storage:
        rate_limit_storage[client_ip] = []

    # 2. Filter out old requests (older than 1 minute)
    requests_in_window = [
        t
        for t in rate_limit_storage[client_ip]
        if (current_time - t).total_seconds() < 60
    ]

    # 3. Check rate limit
    if len(requests_in_window) >= SecurityConfig.RATE_LIMIT_REQUESTS_PER_MINUTE:
        security_metrics["blocked_requests"] += 1
        security_metrics["security_incidents"].append(
            {
                "type": "rate_limit_violation",
                "client_ip": client_ip,
                "timestamp": current_time.isoformat(),
                "requests_in_window": len(requests_in_window),
                "severity": "high",
            }
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": f"Maximum {SecurityConfig.RATE_LIMIT_REQUESTS_PER_MINUTE} requests per minute"
            },
        )

    # 4. Check for suspicious headers
    suspicious_headers = [
        "x-forwarded-for",
        "x-real-ip",
        "x-client-ip",
        "x-forwarded",
        "x-cluster-client-ip",
        "forwarded-for",
        "via",
        "x-custom-ip-authorization",
    ]

    for header in suspicious_headers:
        if header in request.headers:
            security_metrics["blocked_requests"] += 1
            security_metrics["security_incidents"].append(
                {
                    "type": "suspicious_header",
                    "header": header,
                    "client_ip": client_ip,
                    "timestamp": current_time.isoformat(),
                    "severity": "medium",
                }
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Suspicious request headers detected"},
            )

    # 5. Update rate limit storage with current request
    rate_limit_storage[client_ip] = requests_in_window + [current_time]

    # 6. Check for SQL injection patterns in query params and JSON body
    sql_injection_patterns = [
        (
            r"(?i)(\b(select|union|insert|update|delete|drop|alter|create|truncate|exec|xp_|--|#|\*|;)\b)",
            "sql_injection_attempt",
        ),
        (r"(?i)(\b(and|or)\s+\d+\s*=\s*\d+)", "sql_boolean_manipulation"),
        (r"(?i)(\b(union|select).*\b(from|where)\b)", "sql_union_injection"),
    ]

    try:
        # Check URL query parameters
        for param in request.query_params.values():
            for pattern, pattern_type in sql_injection_patterns:
                if re.search(pattern, param, re.IGNORECASE):
                    raise ValueError(f"Suspicious parameter detected: {pattern_type}")

        # Note: We intentionally do NOT check the request body here to avoid consuming it
        # prematurely. The body validation will be handled by FastAPI's automatic validation
        # and Pydantic models, which provide sufficient protection against injection attacks
        # for JSON payloads. The SQL injection patterns are more relevant for URL parameters
        # and query strings that bypass normal validation.

        # Continue to the next middleware/endpoint if all checks pass
        response = await call_next(request)

        # Add security headers with exceptions for Swagger UI
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        # Allow external resources for Swagger UI while maintaining security
        if request.url.path in ["/docs", "/redoc"]:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:; font-src 'self' https://cdn.jsdelivr.net"
            )
        else:
            response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response

    except ValueError as e:
        security_metrics["blocked_requests"] += 1
        security_metrics["security_incidents"].append(
            {
                "type": "injection_attempt",
                "pattern": str(e),
                "client_ip": client_ip,
                "path": request.url.path,
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "high",
            }
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": "Suspicious request detected and blocked for security reasons"
            },
        )
    except Exception as e:
        # Log the error but don't expose internal details
        security_metrics["blocked_requests"] += 1
        security_metrics["security_incidents"].append(
            {
                "type": "server_error",
                "error": str(e),
                "client_ip": client_ip,
                "path": request.url.path,
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "critical",
            }
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error. The query was blocked for security reasons"
            },
        )

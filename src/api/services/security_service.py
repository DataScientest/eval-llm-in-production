"""Security service for tracking metrics and incidents."""

from collections import defaultdict
from datetime import datetime

from services.mlflow_service import mlflow_service

# Rate limiting storage (in production, use Redis)
rate_limit_storage = defaultdict(list)

# Security metrics storage (in production, use proper database)
MAX_INCIDENTS = 1000  # cap to prevent unbounded memory growth
security_metrics = {
    "total_requests": 0,
    "blocked_requests": 0,
    "prompt_injections_detected": 0,
    "content_moderation_triggered": 0,
    "rate_limit_violations": 0,
    "validation_failures": 0,
    "security_incidents": [],
    "last_reset": datetime.now(),
}


def trace_security_incident(
    incident_type: str,
    request_data: dict,
    pattern: str = None,
    error_message: str = None,
):
    """Trace security incidents in MLflow for blocked attacks."""
    # Append with cap to avoid unbounded memory usage
    incidents = security_metrics["security_incidents"]
    if len(incidents) >= MAX_INCIDENTS:
        # drop oldest entry
        incidents.pop(0)
    incidents.append(
        {
            "type": incident_type,
            "data": request_data,
            "pattern": pattern,
            "error_message": error_message,
            "timestamp": datetime.now().isoformat(),
        }
    )
    return mlflow_service.trace_security_incident(
        incident_type, request_data, pattern, error_message
    )


def get_security_metrics():
    """Get current security metrics."""
    return security_metrics.copy()


def reset_security_metrics():
    """Reset security metrics (for testing or periodic resets)."""
    global security_metrics
    security_metrics = {
        "total_requests": 0,
        "blocked_requests": 0,
        "prompt_injections_detected": 0,
        "content_moderation_triggered": 0,
        "rate_limit_violations": 0,
        "validation_failures": 0,
        "security_incidents": [],
        "last_reset": datetime.now(),
    }

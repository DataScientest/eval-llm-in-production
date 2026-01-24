"""System router with comprehensive health checks."""

import logging
from datetime import datetime
from typing import Optional

import httpx
from config.settings import SecurityConfig, settings
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from services.health_checker import health_checker
from services.security_service import security_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
async def health_check():
    """
    Basic liveness health check.

    This endpoint always returns 200 OK if the application is running.
    It does NOT check dependencies - use /health/detailed for that.

    Use this endpoint for:
    - Kubernetes liveness probes
    - Load balancer basic health checks
    - Quick "is the app alive" checks
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/health/detailed")
async def detailed_health_check(
    refresh: bool = Query(False, description="Force refresh cached results"),
):
    """
    Detailed readiness health check with dependency verification.

    Checks all external dependencies:
    - Qdrant (vector database)
    - LiteLLM (LLM proxy)
    - MLflow (tracking server)
    - TEI (embeddings service)

    Returns 200 if all dependencies are healthy, 503 if any are unhealthy.
    Results are cached for 30 seconds to prevent overwhelming dependencies.

    Use this endpoint for:
    - Kubernetes readiness probes
    - Monitoring systems
    - Debugging connectivity issues

    Args:
        refresh: Set to true to bypass cache and force fresh checks
    """
    # Perform health checks
    results = await health_checker.check_all(use_cache=not refresh)

    # Convert results to serializable format
    checks = {}
    for service_name, result in results.items():
        checks[service_name] = {
            "healthy": result.healthy,
            "latency_ms": round(result.latency_ms, 2) if result.latency_ms else None,
            "message": result.message,
            "checked_at": result.checked_at.isoformat() + "Z",
        }

    # Determine overall status
    all_healthy = all(r.healthy for r in results.values())

    # Calculate summary
    healthy_count = sum(1 for r in results.values() if r.healthy)
    total_count = len(results)

    response_data = {
        "status": "healthy" if all_healthy else "degraded",
        "summary": {
            "healthy_services": healthy_count,
            "total_services": total_count,
            "all_healthy": all_healthy,
        },
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    # Return 503 if any dependency is unhealthy
    status_code = 200 if all_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content=response_data,
    )


@router.get("/debug")
async def debug_config():
    """Debug endpoint to show current configuration (non-sensitive)."""
    return {
        "litellm_url": settings.LITELLM_URL,
        "mlflow_uri": settings.MLFLOW_TRACKING_URI,
        "qdrant_url": settings.QDRANT_URL,
        "tei_url": settings.TEI_URL,
        "cache_ttl": settings.CACHE_TTL,
        "using_litellm_proxy": True,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/security-status")
async def security_status():
    """Security status endpoint showing current protection levels."""
    return {
        "security_features": {
            "prompt_injection_detection": True,
            "content_moderation": True,
            "rate_limiting": True,
            "input_validation": True,
            "output_filtering": True,
        },
        "security_config": {
            "max_prompt_length": SecurityConfig.MAX_PROMPT_LENGTH,
            "max_system_prompt_length": SecurityConfig.MAX_SYSTEM_PROMPT_LENGTH,
            "rate_limit_per_minute": SecurityConfig.RATE_LIMIT_REQUESTS_PER_MINUTE,
            "allowed_model_pattern": SecurityConfig.ALLOWED_MODEL_PATTERN,
            "suspicious_patterns_count": len(SecurityConfig.SUSPICIOUS_PATTERNS),
        },
        "guardrails": ["security-guard", "content-filter"],
        "status": "active",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/security-metrics")
async def security_metrics_endpoint():
    """Security metrics endpoint showing real-time security statistics."""
    current_time = datetime.utcnow()
    uptime_seconds = (current_time - security_metrics["last_reset"]).total_seconds()

    # Calculate rates
    requests_per_minute = (
        (security_metrics["total_requests"] / uptime_seconds) * 60
        if uptime_seconds > 0
        else 0
    )
    block_rate = (
        (security_metrics["blocked_requests"] / security_metrics["total_requests"])
        * 100
        if security_metrics["total_requests"] > 0
        else 0
    )

    # Get recent incidents (last 24 hours)
    recent_incidents = [
        incident
        for incident in security_metrics["security_incidents"]
        if (
            current_time - datetime.fromisoformat(incident["timestamp"])
        ).total_seconds()
        < 86400
    ]

    return {
        "overview": {
            "total_requests": security_metrics["total_requests"],
            "blocked_requests": security_metrics["blocked_requests"],
            "success_requests": security_metrics["total_requests"]
            - security_metrics["blocked_requests"],
            "block_rate_percentage": round(block_rate, 2),
            "requests_per_minute": round(requests_per_minute, 2),
        },
        "detailed_metrics": {
            "prompt_injections_detected": security_metrics[
                "prompt_injections_detected"
            ],
            "content_moderation_triggered": security_metrics[
                "content_moderation_triggered"
            ],
            "rate_limit_violations": security_metrics["rate_limit_violations"],
            "validation_failures": security_metrics["validation_failures"],
        },
        "recent_activity": {
            "incidents_last_24h": len(recent_incidents),
            "incident_types_24h": (
                {
                    incident_type: len(
                        [i for i in recent_incidents if i["type"] == incident_type]
                    )
                    for incident_type in set(i["type"] for i in recent_incidents)
                }
                if recent_incidents
                else {}
            ),
        },
        "system_status": {
            "uptime_seconds": round(uptime_seconds),
            "uptime_hours": round(uptime_seconds / 3600, 2),
            "last_reset": security_metrics["last_reset"].isoformat(),
            "security_level": "high",
        },
        "timestamp": current_time.isoformat() + "Z",
    }


@router.get("/cache-metrics")
async def get_cache_metrics():
    """Get Qdrant cache performance metrics."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8000/llm/cache/stats")
            if response.status_code == 200:
                cache_data = response.json()
                return {
                    "message": "Cache metrics retrieved successfully",
                    "redirect_url": "/llm/cache/stats",
                    "cache_data": cache_data,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            else:
                return {
                    "message": "Cache metrics available at /llm/cache/stats",
                    "redirect_url": "/llm/cache/stats",
                    "status": "Cache service may not be ready",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
    except Exception as e:
        logger.warning(f"Could not fetch cache metrics: {e}")
        return {
            "message": "Cache metrics available at /llm/cache/stats",
            "redirect_url": "/llm/cache/stats",
            "error": f"Could not fetch cache data: {str(e)[:100]}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


@router.get("/security-incidents")
async def get_security_incidents(limit: int = Query(50, ge=1, le=1000)):
    """Get detailed security incidents for analysis."""
    recent_incidents = security_metrics["security_incidents"][-limit:]

    return {
        "total_incidents": len(security_metrics["security_incidents"]),
        "showing_recent": len(recent_incidents),
        "incidents": recent_incidents,
        "incident_types": (
            {
                incident_type: len(
                    [i for i in recent_incidents if i["type"] == incident_type]
                )
                for incident_type in set(i["type"] for i in recent_incidents)
            }
            if recent_incidents
            else {}
        ),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

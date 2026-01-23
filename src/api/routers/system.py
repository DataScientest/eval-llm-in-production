"""System router."""

import os
from datetime import datetime
from fastapi import APIRouter

from config.settings import settings, SecurityConfig
from services.security_service import security_metrics
from services.mlflow_service import mlflow_service

router = APIRouter(prefix="/system", tags=["system"]) 


# Root endpoint moved to main app level for Swagger access


@router.get("/health")
async def health_check():
    """Health check endpoint to verify service status."""
    return {"status": "healthy", "timestamp": datetime.now()}


@router.get("/debug")
async def debug_config():
    """Debug endpoint to show current configuration."""
    return {
        "litellm_url": settings.LITELLM_URL,
        "mlflow_uri": settings.MLFLOW_TRACKING_URI,
        "using_litellm_proxy": True,
        "timestamp": datetime.now()
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
            "output_filtering": True
        },
        "security_config": {
            "max_prompt_length": SecurityConfig.MAX_PROMPT_LENGTH,
            "max_system_prompt_length": SecurityConfig.MAX_SYSTEM_PROMPT_LENGTH,
            "rate_limit_per_minute": SecurityConfig.RATE_LIMIT_REQUESTS_PER_MINUTE,
            "allowed_model_pattern": SecurityConfig.ALLOWED_MODEL_PATTERN,
            "suspicious_patterns_count": len(SecurityConfig.SUSPICIOUS_PATTERNS)
        },
        "guardrails": ["security-guard", "content-filter"],
        "status": "active",
        "timestamp": datetime.now()
    }


@router.get("/security-metrics")
async def security_metrics_endpoint():
    """Security metrics endpoint showing real-time security statistics."""
    current_time = datetime.now()
    uptime_seconds = (current_time - security_metrics["last_reset"]).total_seconds()
    
    # Calculate rates
    requests_per_minute = (security_metrics["total_requests"] / uptime_seconds) * 60 if uptime_seconds > 0 else 0
    block_rate = (security_metrics["blocked_requests"] / security_metrics["total_requests"]) * 100 if security_metrics["total_requests"] > 0 else 0
    
    # Get recent incidents (last 24 hours)
    recent_incidents = [
        incident for incident in security_metrics["security_incidents"]
        if (current_time - datetime.fromisoformat(incident["timestamp"])).total_seconds() < 86400
    ]
    
    return {
        "overview": {
            "total_requests": security_metrics["total_requests"],
            "blocked_requests": security_metrics["blocked_requests"],
            "success_requests": security_metrics["total_requests"] - security_metrics["blocked_requests"],
            "block_rate_percentage": round(block_rate, 2),
            "requests_per_minute": round(requests_per_minute, 2)
        },
        "detailed_metrics": {
            "prompt_injections_detected": security_metrics["prompt_injections_detected"],
            "content_moderation_triggered": security_metrics["content_moderation_triggered"],
            "rate_limit_violations": security_metrics["rate_limit_violations"],
            "validation_failures": security_metrics["validation_failures"]
        },
        "recent_activity": {
            "incidents_last_24h": len(recent_incidents),
            "incident_types_24h": {
                incident_type: len([i for i in recent_incidents if i["type"] == incident_type])
                for incident_type in set(i["type"] for i in recent_incidents)
            } if recent_incidents else {}
        },
        "system_status": {
            "uptime_seconds": round(uptime_seconds),
            "uptime_hours": round(uptime_seconds / 3600, 2),
            "last_reset": security_metrics["last_reset"].isoformat(),
            "security_level": "high"
        },
        "timestamp": current_time.isoformat()
    }


@router.get("/cache-metrics")
async def get_cache_metrics():
    """Get Qdrant cache performance metrics. Redirects to LLM cache stats."""
    import httpx
    
    try:
        # Redirect to the new cache stats endpoint
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/llm/cache/stats")
            if response.status_code == 200:
                cache_data = response.json()
                return {
                    "message": "Cache metrics moved to /llm/cache/stats",
                    "redirect_url": "/llm/cache/stats",
                    "cache_data": cache_data,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "message": "Cache metrics available at /llm/cache/stats",
                    "redirect_url": "/llm/cache/stats",
                    "status": "Cache service may not be ready",
                    "timestamp": datetime.now().isoformat()
                }
    except Exception as e:
        return {
            "message": "Cache metrics moved to /llm/cache/stats",
            "redirect_url": "/llm/cache/stats",
            "error": f"Could not fetch cache data: {e}",
            "timestamp": datetime.now().isoformat()
        }


@router.get("/security-incidents")
async def get_security_incidents(limit: int = 50):
    """Get detailed security incidents with full prompts for analysis."""
    recent_incidents = security_metrics["security_incidents"][-limit:]
    
    return {
        "total_incidents": len(security_metrics["security_incidents"]),
        "showing_recent": len(recent_incidents),
        "incidents": recent_incidents,
        "incident_types": {
            incident_type: len([i for i in recent_incidents if i["type"] == incident_type])
            for incident_type in set(i["type"] for i in recent_incidents)
        },
        "timestamp": datetime.now().isoformat()
    }
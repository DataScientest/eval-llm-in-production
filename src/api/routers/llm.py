"""LLM operations router - thin adapter over LLMService."""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import openai
import requests

from fastapi import APIRouter, Depends, HTTPException, status
from models.llm_models import ModelsResponse, SecurePromptRequest, SecurePromptResponse
from services.auth_service import verify_token
from services.circuit_breaker import litellm_circuit
from services.llm_service import get_llm_service, LLMService
from services.mlflow_service import mlflow_service
from services.security_service import security_metrics
from metrics.cache_metrics import record_performance_savings
from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm"])

# Constants for error handling
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30.0


def generate_incident_id() -> str:
    """Generate a unique incident ID for error tracking."""
    return f"inc_{uuid.uuid4().hex[:12]}"


def create_error_response(
    error_type: str,
    message: str,
    status_code: int,
    incident_id: Optional[str] = None,
    **extra_fields,
) -> dict:
    """Create a standardized error response with incident tracking."""
    response = {
        "error": error_type,
        "message": message,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    if incident_id:
        response["incident_id"] = incident_id
    response.update(extra_fields)
    return response


@router.post("/generate", response_model=SecurePromptResponse)
async def generate_secure_prompt(
    request: SecurePromptRequest,
    current_user: Dict[str, Any] = Depends(verify_token),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Generate text using LLM with security guardrails, timeouts, retry, and circuit breaker."""
    start_time = time.time()
    incident_id = None

    # Check circuit breaker before making request
    if not await litellm_circuit.can_execute():
        incident_id = generate_incident_id()
        logger.warning(f"[{incident_id}] LiteLLM circuit breaker is open, failing fast")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_error_response(
                error_type="ServiceUnavailable",
                message="LLM service is experiencing issues. Please retry later.",
                status_code=503,
                incident_id=incident_id,
                circuit_state=litellm_circuit.state.value,
                retry_after=int(litellm_circuit.recovery_timeout),
            ),
            headers={"Retry-After": str(int(litellm_circuit.recovery_timeout))},
        )

    try:
        # Prepare messages for the LLM
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        logger.debug(f"Making LiteLLM request with model: {request.model}")

        # Use LLM service for generation (handles caching, retries, cost calculation)
        llm_response = await llm_service.generate(
            messages=messages,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            system_prompt=request.system_prompt,
        )

        # Update cache performance metrics
        if llm_response.cache_hit:
            estimated_llm_time_ms = 3000
            time_saved_ms = estimated_llm_time_ms - (llm_response.cache_latency_ms or 0)
            record_performance_savings("exact", time_saved_ms)

        # Trace in MLflow (with fallback on failure)
        try:
            tokens_dict = {
                "prompt_tokens": llm_response.prompt_tokens,
                "completion_tokens": llm_response.completion_tokens,
                "total_tokens": llm_response.total_tokens,
            }
            mlflow_service.trace_llm_request(
                prompt=request.prompt,
                model=request.model,
                response=llm_response.response_text,
                tokens=tokens_dict,
                cost=llm_response.cost,
                start_time=start_time,
                cache_hit=llm_response.cache_hit,
                cache_latency_ms=llm_response.cache_latency_ms,
                cache_type=llm_response.cache_type,
            )
        except Exception as e:
            logger.warning(f"MLflow tracing failed (non-critical): {e}")

        return SecurePromptResponse(
            response=llm_response.response_text,
            model=request.model,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            total_tokens=llm_response.total_tokens,
            cost=llm_response.cost,
            security_status="protected",
            guardrails_triggered=llm_response.guardrails_triggered,
        )

    except HTTPException:
        raise

    except asyncio.TimeoutError as e:
        await litellm_circuit.record_failure(e)
        security_metrics["blocked_requests"] += 1
        incident_id = generate_incident_id()
        logger.error(f"[{incident_id}] LiteLLM request timed out after retries: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=create_error_response(
                error_type="GatewayTimeout",
                message=f"LLM request timed out after {MAX_RETRIES + 1} attempts",
                status_code=504,
                incident_id=incident_id,
                timeout_seconds=REQUEST_TIMEOUT,
                attempts=MAX_RETRIES + 1,
            ),
        )

    except openai.APITimeoutError as e:
        await litellm_circuit.record_failure(e)
        security_metrics["blocked_requests"] += 1
        incident_id = generate_incident_id()
        logger.error(f"[{incident_id}] LiteLLM timeout after retries: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=create_error_response(
                error_type="GatewayTimeout",
                message="LLM service timed out",
                status_code=504,
                incident_id=incident_id,
            ),
        )

    except openai.APIConnectionError as e:
        await litellm_circuit.record_failure(e)
        security_metrics["blocked_requests"] += 1
        incident_id = generate_incident_id()
        logger.error(f"[{incident_id}] LiteLLM connection error after retries: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=create_error_response(
                error_type="BadGateway",
                message="Could not connect to LLM service after multiple attempts",
                status_code=502,
                incident_id=incident_id,
            ),
        )

    except openai.RateLimitError as e:
        security_metrics["blocked_requests"] += 1
        incident_id = generate_incident_id()
        logger.warning(f"[{incident_id}] Rate limit exceeded: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=create_error_response(
                error_type="RateLimitExceeded",
                message="Too many requests. Please try again later.",
                status_code=429,
                incident_id=incident_id,
                retry_after=60,
            ),
            headers={"Retry-After": "60"},
        )

    except openai.BadRequestError as e:
        security_metrics["blocked_requests"] += 1
        incident_id = generate_incident_id()
        logger.warning(f"[{incident_id}] Bad request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                error_type="BadRequest",
                message=str(e),
                status_code=400,
                incident_id=incident_id,
            ),
        )

    except openai.AuthenticationError as e:
        security_metrics["blocked_requests"] += 1
        incident_id = generate_incident_id()
        logger.error(f"[{incident_id}] Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response(
                error_type="AuthenticationError",
                message="LLM service authentication failed",
                status_code=401,
                incident_id=incident_id,
            ),
        )

    except openai.PermissionDeniedError as e:
        security_metrics["blocked_requests"] += 1
        incident_id = generate_incident_id()
        logger.error(f"[{incident_id}] Permission denied: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                error_type="PermissionDenied",
                message="Access to requested model denied",
                status_code=403,
                incident_id=incident_id,
            ),
        )

    except openai.NotFoundError as e:
        security_metrics["blocked_requests"] += 1
        incident_id = generate_incident_id()
        logger.warning(f"[{incident_id}] Model not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                error_type="NotFound",
                message=f"Model '{request.model}' not found",
                status_code=404,
                incident_id=incident_id,
                requested_model=request.model,
            ),
        )

    except Exception as e:
        await litellm_circuit.record_failure(e)
        security_metrics["blocked_requests"] += 1
        incident_id = generate_incident_id()
        logger.error(f"[{incident_id}] Unexpected error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                error_type="InternalServerError",
                message="An unexpected error occurred. Please try again.",
                status_code=500,
                incident_id=incident_id,
            ),
        )


# Cache management endpoints
@router.get("/cache/stats")
async def get_cache_stats(
    current_user: Dict[str, Any] = Depends(verify_token),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Get cache statistics."""
    try:
        stats = llm_service.get_cache_stats()
        return {"status": "success", "data": stats}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting cache stats: {e}",
        )


@router.delete("/cache/clear")
async def clear_cache(
    cache_type: str = "all",
    current_user: Dict[str, Any] = Depends(verify_token),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Clear cache collections."""
    try:
        success = llm_service._cache.clear_cache(cache_type)
        if success:
            return {
                "status": "success",
                "message": f"Cache '{cache_type}' cleared successfully",
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to clear cache",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing cache: {e}",
        )


@router.get("/models", response_model=ModelsResponse)
async def list_models():
    """List all available models from the LiteLLM router."""
    try:
        response = requests.get(
            f"{settings.LITELLM_URL}/models", timeout=CONNECT_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout fetching models from LiteLLM",
        )
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error fetching models: {e}",
        )


@router.get("/v1/models", response_model=ModelsResponse)
async def list_models_v1():
    """OpenAI-compatible models endpoint for better API compatibility."""
    return await list_models()


@router.get("/health")
async def llm_health():
    """LLM service health check with circuit breaker status."""
    from services.circuit_breaker import get_all_circuit_breakers

    return {
        "status": "healthy",
        "service": "llm",
        "circuit_breakers": get_all_circuit_breakers(),
    }

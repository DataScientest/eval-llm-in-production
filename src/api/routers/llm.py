"""LLM operations router with timeouts and circuit breaker."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
import openai
import requests

# Import our exact cache
from cache.exact_cache import ExactCache
from config.settings import settings
from fastapi import APIRouter, Depends, HTTPException, status
from models.llm_models import ModelsResponse, SecurePromptRequest, SecurePromptResponse
from services.auth_service import verify_token
from services.circuit_breaker import CircuitBreakerError, litellm_circuit
from services.mlflow_service import mlflow_service
from services.security_service import security_metrics

from litellm import completion_cost

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm"])

# Timeout configuration
CONNECT_TIMEOUT = 5.0  # 5 seconds for connection
REQUEST_TIMEOUT = 30.0  # 30 seconds for request completion

# Configure OpenAI client to use LiteLLM proxy WITH TIMEOUTS
client = openai.OpenAI(
    base_url=f"{settings.LITELLM_URL}/v1",
    api_key="dummy-key",  # LiteLLM handles the real API keys
    timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT),
    max_retries=0,  # We handle retries ourselves
)

# Initialize exact cache
cache = ExactCache(
    qdrant_url=settings.QDRANT_URL,
    ttl_seconds=1800,
)


@router.post("/generate", response_model=SecurePromptResponse)
async def generate_secure_prompt(
    request: SecurePromptRequest, current_user: Dict[str, Any] = Depends(verify_token)
):
    """Generate text using LLM with built-in security guardrails, timeouts, and circuit breaker."""
    start_time = time.time()

    # Check circuit breaker before making request
    if not await litellm_circuit.can_execute():
        logger.warning("LiteLLM circuit breaker is open, failing fast")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service temporarily unavailable",
                "message": "LLM service is experiencing issues. Please retry later.",
                "circuit_state": litellm_circuit.state.value,
                "retry_after": int(litellm_circuit.recovery_timeout),
            },
            headers={"Retry-After": str(int(litellm_circuit.recovery_timeout))},
        )

    try:
        # Prepare messages for the LLM
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        # Prepare request parameters
        litellm_params = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        # Add structured output if specified
        if request.response_format:
            litellm_params["response_format"] = request.response_format

        logger.debug(f"Making LiteLLM request with model: {request.model}")

        # Create cache key from full prompt
        full_prompt = "\n".join([msg["content"] for msg in messages])

        # Try exact cache first
        cached_response = cache.get(
            prompt=full_prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        if cached_response:
            logger.info("Exact cache hit")
            response_text = cached_response["response"]
            prompt_tokens = cached_response["prompt_tokens"]
            completion_tokens = cached_response["completion_tokens"]
            total_tokens = cached_response["total_tokens"]
            cost = cached_response["cost"]
            guardrails_triggered = cached_response.get("guardrails_triggered", [])
        else:
            # No exact cache hit, call LiteLLM with timeout
            logger.debug("No exact cache hit, calling LiteLLM")

            try:
                # Use asyncio timeout for additional protection
                async with asyncio.timeout(REQUEST_TIMEOUT + 5):
                    # The OpenAI client call is synchronous, run in executor
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None, lambda: client.chat.completions.create(**litellm_params)
                    )
            except asyncio.TimeoutError:
                await litellm_circuit.record_failure()
                logger.error(f"LiteLLM request timed out after {REQUEST_TIMEOUT}s")
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail={
                        "error": "Gateway Timeout",
                        "message": f"LLM request timed out after {REQUEST_TIMEOUT} seconds",
                        "timeout_seconds": REQUEST_TIMEOUT,
                    },
                )

            # Extract response data
            response_text = response.choices[0].message.content
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            # Calculate cost
            try:
                actual_model = (
                    response.model if hasattr(response, "model") else request.model
                )
                cost = completion_cost(completion_response=response, model=actual_model)
            except Exception as e:
                logger.warning(f"Could not calculate cost for {request.model}: {e}")
                cost = (prompt_tokens * 0.00001) + (completion_tokens * 0.00002)

            # Check for triggered guardrails
            guardrails_triggered = []
            if hasattr(response, "guardrails_triggered"):
                guardrails_triggered = response.guardrails_triggered

            # Store in exact cache
            response_data = {
                "response": response_text,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost": cost,
                "guardrails_triggered": guardrails_triggered,
            }

            cache.set(
                prompt=full_prompt,
                model=request.model,
                response=response_data,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            # Record success for circuit breaker
            await litellm_circuit.record_success()

        # Calculate metrics
        end_time = time.time()
        response_time = end_time - start_time

        # Determine cache status
        cache_hit = cached_response is not None
        cache_latency_ms = response_time * 1000 if cached_response else None
        cache_type = "exact" if cached_response else None

        # Trace in MLflow
        try:
            tokens_dict = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
            mlflow_service.trace_llm_request(
                prompt=request.prompt,
                model=request.model,
                response=response_text,
                tokens=tokens_dict,
                cost=cost,
                start_time=start_time,
                cache_hit=cache_hit,
                cache_latency_ms=cache_latency_ms,
                cache_type=cache_type,
            )
        except Exception as e:
            logger.warning(f"Could not trace LLM request: {e}")

        return SecurePromptResponse(
            response=response_text,
            model=request.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            security_status="protected",
            guardrails_triggered=guardrails_triggered,
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except openai.APITimeoutError as e:
        await litellm_circuit.record_failure(e)
        security_metrics["blocked_requests"] += 1
        logger.error(f"LiteLLM timeout: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error": "Gateway Timeout",
                "message": f"LLM service timed out after {REQUEST_TIMEOUT} seconds",
            },
        )
    except openai.APIConnectionError as e:
        await litellm_circuit.record_failure(e)
        security_metrics["blocked_requests"] += 1
        logger.error(f"LiteLLM connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "Bad Gateway",
                "message": "Could not connect to LLM service",
            },
        )
    except openai.RateLimitError as e:
        security_metrics["blocked_requests"] += 1
        logger.warning(f"Rate limit exceeded: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate Limit Exceeded",
                "message": "Too many requests. Please try again later.",
                "retry_after": 60,
            },
            headers={"Retry-After": "60"},
        )
    except openai.BadRequestError as e:
        security_metrics["blocked_requests"] += 1
        logger.warning(f"Bad request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Bad Request",
                "message": str(e),
            },
        )
    except Exception as e:
        await litellm_circuit.record_failure(e)
        security_metrics["blocked_requests"] += 1
        logger.error(f"Error generating response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal Server Error",
                "message": "Failed to generate response. Please try again.",
            },
        )


# Cache management endpoints
@router.get("/cache/stats")
async def get_cache_stats(current_user: Dict[str, Any] = Depends(verify_token)):
    """Get cache statistics."""
    try:
        stats = cache.get_cache_stats()
        return {"status": "success", "data": stats}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting cache stats: {e}",
        )


@router.delete("/cache/clear")
async def clear_cache(
    cache_type: str = "all", current_user: Dict[str, Any] = Depends(verify_token)
):
    """Clear cache collections."""
    try:
        success = cache.clear_cache(cache_type)
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

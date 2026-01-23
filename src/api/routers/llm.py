"""LLM operations router with timeouts, circuit breaker, and retry logic."""

import asyncio
import logging
import time
import uuid
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
from services.circuit_breaker import litellm_circuit
from services.mlflow_service import mlflow_service
from services.security_service import security_metrics
from utils.retry import calculate_backoff_delay, retry_with_backoff

from litellm import completion_cost

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm"])

# Timeout configuration
CONNECT_TIMEOUT = 5.0  # 5 seconds for connection
REQUEST_TIMEOUT = 30.0  # 30 seconds for request completion

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # 1 second

# Retryable OpenAI exceptions (transient errors)
RETRYABLE_OPENAI_ERRORS = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)

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


async def call_llm_with_retry(litellm_params: dict) -> Any:
    """
    Call LLM with retry logic for transient errors.

    Implements exponential backoff with jitter for retries.
    """
    last_exception = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            # Use asyncio timeout for additional protection
            async with asyncio.timeout(REQUEST_TIMEOUT + 5):
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, lambda: client.chat.completions.create(**litellm_params)
                )
                return response

        except RETRYABLE_OPENAI_ERRORS as e:
            last_exception = e

            if attempt >= MAX_RETRIES:
                logger.error(
                    f"All {MAX_RETRIES + 1} attempts failed: {type(e).__name__}: {e}"
                )
                raise

            delay = calculate_backoff_delay(
                attempt=attempt,
                base_delay=RETRY_BASE_DELAY,
            )

            logger.warning(
                f"Attempt {attempt + 1}/{MAX_RETRIES + 1} failed: {type(e).__name__}. "
                f"Retrying in {delay:.2f}s..."
            )

            await asyncio.sleep(delay)

        except asyncio.TimeoutError:
            # Timeout is also retryable
            last_exception = asyncio.TimeoutError(
                f"Request timed out after {REQUEST_TIMEOUT}s"
            )

            if attempt >= MAX_RETRIES:
                logger.error(f"All {MAX_RETRIES + 1} attempts timed out")
                raise

            delay = calculate_backoff_delay(
                attempt=attempt, base_delay=RETRY_BASE_DELAY
            )
            logger.warning(
                f"Attempt {attempt + 1}/{MAX_RETRIES + 1} timed out. "
                f"Retrying in {delay:.2f}s..."
            )
            await asyncio.sleep(delay)

    # Should not reach here
    if last_exception:
        raise last_exception


@router.post("/generate", response_model=SecurePromptResponse)
async def generate_secure_prompt(
    request: SecurePromptRequest, current_user: Dict[str, Any] = Depends(verify_token)
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

        # Prepare request parameters
        litellm_params = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

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
            # No exact cache hit, call LiteLLM with retry
            logger.debug("No exact cache hit, calling LiteLLM with retry")

            response = await call_llm_with_retry(litellm_params)

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

        cache_hit = cached_response is not None
        cache_latency_ms = response_time * 1000 if cached_response else None
        cache_type = "exact" if cached_response else None

        # Trace in MLflow (with fallback on failure)
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
            # MLflow failure is non-critical - log and continue
            logger.warning(f"MLflow tracing failed (non-critical): {e}")
            # Could also write to local file as fallback here

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

"""LLM operations router.

TODO Exercise 3: No timeouts configured!
- OpenAI client has no timeout -> can hang forever
- No circuit breaker -> cascading failures
- No request body size limits

TODO Exercise 4: Poor error handling!
- Generic exception catching
- No retry logic for transient errors
- No incident tracking
- print() instead of proper logging

Students should:
- Add timeouts to OpenAI client (30s request, 5s connect)
- Implement circuit breaker pattern
- Add retry with exponential backoff
- Create granular error handling by exception type
- Add incident IDs for error tracking
"""

import time
from typing import Any, Dict

import openai
import requests
from litellm import completion_cost

from fastapi import APIRouter, Depends, HTTPException, status
from models.llm_models import ModelsResponse, SecurePromptRequest, SecurePromptResponse
from services.auth_service import verify_token
from services.mlflow_service import mlflow_service
from services.security_service import security_metrics
from config.settings import settings
from cache.exact_cache import ExactCache

router = APIRouter(prefix="/llm", tags=["llm"])

# TODO Exercise 3: No timeout configured! This can hang forever!
client = openai.OpenAI(
    base_url=f"{settings.LITELLM_URL}/v1",
    api_key="dummy-key"  # LiteLLM handles the real API keys
)

# Initialize exact cache
cache = ExactCache(
    qdrant_url=settings.QDRANT_URL,
    ttl_seconds=1800,
)


@router.post("/generate", response_model=SecurePromptResponse)
async def generate_secure_prompt(
    request: SecurePromptRequest,
    current_user: Dict[str, Any] = Depends(verify_token)
):
    """Generate text using LLM with built-in security guardrails."""
    start_time = time.time()

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
            "max_tokens": request.max_tokens
        }

        if request.response_format:
            litellm_params["response_format"] = request.response_format

        print(f"DEBUG: Making LiteLLM request with model: {request.model}")

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
            print("Exact cache hit")
            response_text = cached_response["response"]
            prompt_tokens = cached_response["prompt_tokens"]
            completion_tokens = cached_response["completion_tokens"]
            total_tokens = cached_response["total_tokens"]
            cost = cached_response["cost"]
            guardrails_triggered = cached_response.get("guardrails_triggered", [])
        else:
            response = client.chat.completions.create(**litellm_params)

            response_text = response.choices[0].message.content
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            try:
                actual_model = response.model if hasattr(response, "model") else request.model
                cost = completion_cost(completion_response=response, model=actual_model)
            except Exception as e:
                print(f"Warning: Could not calculate cost: {e}")
                cost = (prompt_tokens * 0.00001) + (completion_tokens * 0.00002)

            guardrails_triggered = []

            cache.set(
                prompt=full_prompt,
                model=request.model,
                response={
                    "response": response_text,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost": cost,
                    "guardrails_triggered": guardrails_triggered,
                },
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

        # Trace in MLflow
        try:
            mlflow_service.trace_llm_request(
                prompt=request.prompt,
                model=request.model,
                response=response_text,
                tokens={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": total_tokens},
                cost=cost,
                start_time=start_time,
                cache_hit=cached_response is not None,
            )
        except Exception as e:
            # TODO Exercise 4: Silent failure - no fallback logging!
            print(f"Warning: Could not trace LLM request: {e}")

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

    except Exception as e:
        print(f"Error generating response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate response"
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
    cache_type: str = "all",
    current_user: Dict[str, Any] = Depends(verify_token)
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
        response = requests.get(f"{settings.LITELLM_URL}/models", timeout=5)
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
    """LLM service health check."""
    return {
        "status": "healthy",
        "service": "llm",
    }

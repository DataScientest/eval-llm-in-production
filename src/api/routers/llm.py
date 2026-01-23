"""LLM operations router."""

import time
import requests
import openai
import litellm
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from litellm import completion_cost

# Import our exact cache
from cache.exact_cache import ExactCache

from models.llm_models import SecurePromptRequest, SecurePromptResponse, ModelsResponse
from services.auth_service import verify_token
from services.mlflow_service import mlflow_service
from services.security_service import security_metrics

from config.settings import settings

router = APIRouter(prefix="/llm", tags=["llm"])

# Configure OpenAI client to use LiteLLM proxy
client = openai.OpenAI(
    base_url=f"{settings.LITELLM_URL}/v1",
    api_key="dummy-key"  # LiteLLM handles the real API keys
)

# Initialize exact cache
# Note: Only exact cache is managed locally, semantic cache is handled by LiteLLM
cache = ExactCache(
    qdrant_url=settings.QDRANT_URL,
    ttl_seconds=1800,
)


@router.post("/generate", response_model=SecurePromptResponse)
async def generate_secure_prompt(
    request: SecurePromptRequest, 
    current_user: Dict[str, Any] = Depends(verify_token)
):
    """Generate text using LLM with built-in security guardrails and MLflow tracing."""
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
        
        # Add structured output if specified
        if request.response_format:
            litellm_params["response_format"] = request.response_format
        
        # Note: guardrails are handled by our security validation, not passed to LiteLLM
        # The security validation happens in the Pydantic models and middleware
        
        print(f"DEBUG: Making LiteLLM request with model: {request.model}")
        print(f"DEBUG: Messages: {messages}")
        
        # Create cache key from full prompt
        full_prompt = "\n".join([msg["content"] for msg in messages])
        cache_params = {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "response_format": request.response_format
        }
        
        # Try exact cache first
        cached_response = cache.get(
            prompt=full_prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        if cached_response:
            print("DEBUG: Exact cache hit!")
            response_text = cached_response["response"]
            prompt_tokens = cached_response["prompt_tokens"]
            completion_tokens = cached_response["completion_tokens"]
            total_tokens = cached_response["total_tokens"]
            cost = cached_response["cost"]
            guardrails_triggered = cached_response.get("guardrails_triggered", [])
        else:
            # No exact cache hit, let LiteLLM handle semantic cache + LLM call
            print("DEBUG: No exact cache hit, calling LiteLLM (semantic cache + LLM)")
            response = client.chat.completions.create(**litellm_params)
            
            # Extract response data
            response_text = response.choices[0].message.content
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            
            # Calculate cost
            try:
                # Try to get the underlying model from LiteLLM response
                actual_model = response.model if hasattr(response, 'model') else request.model
                cost = completion_cost(
                    completion_response=response,
                    model=actual_model
                )
            except Exception as e:
                print(f"Warning: Could not calculate cost for {request.model}: {e}")
                # Fallback cost calculation based on token usage
                cost = (prompt_tokens * 0.00001) + (completion_tokens * 0.00002)
                
            # Check for triggered guardrails (outside of except block)
            guardrails_triggered = []
            if hasattr(response, 'guardrails_triggered'):
                guardrails_triggered = response.guardrails_triggered
            
            # Store in exact cache (outside of except block)
            response_data = {
                "response": response_text,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost": cost,
                "guardrails_triggered": guardrails_triggered
            }
            
            # Store in exact cache for future exact matches
            cache.set(
                prompt=full_prompt,
                model=request.model,
                response=response_data,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
        
        # Calculate metrics
        end_time = time.time()
        response_time = end_time - start_time
        
        # Determine cache status and cache latency
        cache_hit = cached_response is not None
        cache_latency_ms = None
        cache_type = None
        
        if cached_response:
            cache_latency_ms = response_time * 1000  # Convert to milliseconds
            cache_type = "exact"
        
        # Trace in MLflow with cache information
        try:
            tokens_dict = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
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
                cache_type=cache_type
            )
        except Exception as e:
            print(f"Warning: Could not trace LLM request: {e}")
        
        # Guardrails are already handled in cache data or set above
        
        return SecurePromptResponse(
            response=response_text,
            model=request.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            security_status="protected",
            guardrails_triggered=guardrails_triggered
        )
        
    except openai.RateLimitError as e:
        security_metrics["blocked_requests"] += 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    except openai.BadRequestError as e:
        security_metrics["blocked_requests"] += 1
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        security_metrics["blocked_requests"] += 1
        print(f"Error generating response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate response. Please try again."
        )


# Cache management endpoints
@router.get("/cache/stats")
async def get_cache_stats(current_user: Dict[str, Any] = Depends(verify_token)):
    """Get cache statistics."""
    try:
        stats = cache.get_cache_stats()
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting cache stats: {e}"
        )

@router.delete("/cache/clear")
async def clear_cache(
    cache_type: str = "all",  # "exact", "semantic", or "all"
    current_user: Dict[str, Any] = Depends(verify_token)
):
    """Clear cache collections."""
    try:
        success = cache.clear_cache(cache_type)
        if success:
            return {
                "status": "success",
                "message": f"Cache '{cache_type}' cleared successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to clear cache"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing cache: {e}"
        )

@router.get("/models", response_model=ModelsResponse)
async def list_models():
    """List all available models from the LiteLLM router."""
    try:
        response = requests.get(f"{settings.LITELLM_URL}/models")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching models: {e}")


# Add OpenAI-compatible v1 endpoints
@router.get("/v1/models", response_model=ModelsResponse)
async def list_models_v1():
    """OpenAI-compatible models endpoint for better API compatibility."""
    return await list_models()


@router.get("/health")
async def llm_health():
    """LLM service health check."""
    return {"status": "healthy", "service": "llm"}
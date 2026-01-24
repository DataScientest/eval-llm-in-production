"""LLM service with timeouts, circuit breaker, retry logic, and cache management."""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import openai
from litellm import completion_cost

from cache.exact_cache import ExactCache
from config.settings import settings
from metrics.cache_metrics import (
    record_cache_hit,
    record_cache_miss,
    record_performance_savings,
    update_cache_ratio,
)
from services.circuit_breaker import litellm_circuit
from utils.retry import calculate_backoff_delay

logger = logging.getLogger(__name__)


# Configuration
CONNECT_TIMEOUT = 5.0
REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0

RETRYABLE_OPENAI_ERRORS = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)


@dataclass
class LLMResponse:
    """Structured response from LLM service."""
    response_text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    cache_hit: bool
    cache_type: Optional[str]
    cache_latency_ms: Optional[float]
    guardrails_triggered: List[str]


class LLMService:
    """Service for LLM operations with caching, retries, and circuit breaker."""

    def __init__(
        self,
        litellm_url: str = None,
        qdrant_url: str = None,
        cache_ttl: int = 1800,
    ):
        self.litellm_url = litellm_url or settings.LITELLM_URL
        self.qdrant_url = qdrant_url or settings.QDRANT_URL
        self.cache_ttl = cache_ttl

        # Initialize OpenAI client pointing to LiteLLM proxy
        self._client = openai.OpenAI(
            base_url=f"{self.litellm_url}/v1",
            api_key="dummy-key",
            timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT),
            max_retries=0,
        )

        # Initialize exact cache
        self._cache = ExactCache(
            qdrant_url=self.qdrant_url,
            ttl_seconds=cache_ttl,
        )

    @staticmethod
    def generate_incident_id() -> str:
        """Generate a unique incident ID for error tracking."""
        return f"inc_{uuid.uuid4().hex[:12]}"

    async def _call_llm_with_retry(self, params: dict) -> Any:
        """Call LLM with retry logic for transient errors."""
        last_exception = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                async with asyncio.timeout(REQUEST_TIMEOUT + 5):
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None, lambda: self._client.chat.completions.create(**params)
                    )
                    return response

            except RETRYABLE_OPENAI_ERRORS as e:
                last_exception = e
                if attempt >= MAX_RETRIES:
                    logger.error(f"All {MAX_RETRIES + 1} attempts failed: {type(e).__name__}: {e}")
                    raise

                delay = calculate_backoff_delay(attempt=attempt, base_delay=RETRY_BASE_DELAY)
                logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES + 1} failed: {type(e).__name__}. Retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)

            except asyncio.TimeoutError:
                last_exception = asyncio.TimeoutError(f"Request timed out after {REQUEST_TIMEOUT}s")
                if attempt >= MAX_RETRIES:
                    logger.error(f"All {MAX_RETRIES + 1} attempts timed out")
                    raise

                delay = calculate_backoff_delay(attempt=attempt, base_delay=RETRY_BASE_DELAY)
                logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES + 1} timed out. Retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)

        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected state in retry loop")

    def _calculate_cost(self, response: Any, model: str) -> float:
        """Calculate the cost of an LLM response."""
        try:
            actual_model = response.model if hasattr(response, "model") else model
            return completion_cost(completion_response=response, model=actual_model)
        except Exception as e:
            logger.warning(f"Could not calculate cost for {model}: {e}")
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            return (prompt_tokens * 0.00001) + (completion_tokens * 0.00002)

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 100,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """
        Generate a response from the LLM with caching and retry logic.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system_prompt: Optional system prompt to prepend
            
        Returns:
            LLMResponse with all response data
        """
        start_time = time.time()

        # Build full prompt for cache key
        full_prompt = "\n".join([msg["content"] for msg in messages])

        # Try exact cache first
        cache_lookup_start = time.time()
        cached_response = self._cache.get(
            prompt=full_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        cache_lookup_time = time.time() - cache_lookup_start

        if cached_response:
            logger.info("Exact cache hit")
            record_cache_hit("exact", cache_lookup_time)

            return LLMResponse(
                response_text=cached_response["response"],
                model=model,
                prompt_tokens=cached_response["prompt_tokens"],
                completion_tokens=cached_response["completion_tokens"],
                total_tokens=cached_response["total_tokens"],
                cost=cached_response["cost"],
                cache_hit=True,
                cache_type="exact",
                cache_latency_ms=cache_lookup_time * 1000,
                guardrails_triggered=cached_response.get("guardrails_triggered", []),
            )

        # No cache hit - call LLM
        logger.debug("No exact cache hit, calling LiteLLM with retry")
        record_cache_miss()

        litellm_params = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        response = await self._call_llm_with_retry(litellm_params)

        # Extract response data
        response_text = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        cost = self._calculate_cost(response, model)

        guardrails_triggered = []
        if hasattr(response, "guardrails_triggered"):
            guardrails_triggered = response.guardrails_triggered

        # Store in cache
        response_data = {
            "response": response_text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
            "guardrails_triggered": guardrails_triggered,
        }

        self._cache.set(
            prompt=full_prompt,
            model=model,
            response=response_data,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Record circuit breaker success
        await litellm_circuit.record_success()

        # Update cache metrics
        end_time = time.time()
        response_time = end_time - start_time

        try:
            from prometheus_client import REGISTRY
            exact_hits = REGISTRY.get_sample_value('llmops_cache_hits_total', {'cache_type': 'exact'}) or 0
            misses = REGISTRY.get_sample_value('llmops_cache_hits_total', {'cache_type': 'miss'}) or 0
            update_cache_ratio(exact_hits, misses)
        except Exception:
            pass

        return LLMResponse(
            response_text=response_text,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            cache_hit=False,
            cache_type=None,
            cache_latency_ms=None,
            guardrails_triggered=guardrails_triggered,
        )

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_cache_stats()


# Default service instance (can be overridden for testing)
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service instance (dependency injection)."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def set_llm_service(service: LLMService) -> None:
    """Set the LLM service instance (for testing)."""
    global _llm_service
    _llm_service = service

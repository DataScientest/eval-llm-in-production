"""Tests for the Redis cache service."""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch
import json
import time
from services.cache_service import CacheService

@pytest_asyncio.fixture
async def cache_service():
    """Create a cache service instance for testing."""
    service = CacheService()
    await service.initialize()
    try:
        yield service
    finally:
        # Cleanup after tests
        if service.redis:
            await service.redis.flushall()
            await service.redis.close()

@pytest.mark.asyncio
async def test_cache_service_initialization():
    """Test cache service initialization."""
    service = CacheService()
    await service.initialize()
    assert service.redis is not None
    assert await service.redis.ping() is True

@pytest.mark.asyncio
async def test_cache_key_generation(cache_service):
    """Test cache key generation consistency."""
    prompt = "Test prompt"
    model = "test-model"
    params = {
        "temperature": 0.7,
        "max_tokens": 100,
        "system_prompt": "You are a helpful assistant"
    }
    
    key1 = cache_service._generate_cache_key(prompt, model, **params)
    key2 = cache_service._generate_cache_key(prompt, model, **params)
    
    assert key1 == key2
    assert "test-model" in key1
    assert key1.startswith("llmops:cache:v1:")

@pytest.mark.asyncio
async def test_cache_store_and_retrieve(cache_service):
    """Test storing and retrieving from cache."""
    prompt = "What is the meaning of life?"
    model = "test-model"
    test_response = {
        "response": "42",
        "total_tokens": 100,
        "cost": 0.002
    }
    
    # Store in cache
    success = await cache_service.store_response(
        prompt=prompt,
        model=model,
        response=test_response
    )
    assert success is True
    
    # Retrieve from cache
    cached_response, latency = await cache_service.get_cached_response(
        prompt=prompt,
        model=model
    )
    
    assert cached_response is not None
    assert cached_response["response"] == "42"
    assert isinstance(latency, float)
    assert latency > 0

@pytest.mark.asyncio
async def test_cache_miss(cache_service):
    """Test cache miss behavior."""
    prompt = "This prompt is not cached"
    model = "test-model"
    
    response, latency = await cache_service.get_cached_response(
        prompt=prompt,
        model=model
    )
    
    assert response is None
    assert latency is None
    assert cache_service.metrics["misses"] == 1

@pytest.mark.asyncio
async def test_adaptive_ttl(cache_service):
    """Test adaptive TTL calculation."""
    expensive_response = {"cost": 0.02, "total_tokens": 100}
    medium_response = {"cost": 0.007, "total_tokens": 100}
    long_response = {"cost": 0.001, "total_tokens": 1500}
    basic_response = {"cost": 0.001, "total_tokens": 100}
    
    # Test TTL scaling
    assert cache_service._calculate_adaptive_ttl(expensive_response) > \
           cache_service._calculate_adaptive_ttl(basic_response)
    assert cache_service._calculate_adaptive_ttl(medium_response) > \
           cache_service._calculate_adaptive_ttl(basic_response)
    assert cache_service._calculate_adaptive_ttl(long_response) > \
           cache_service._calculate_adaptive_ttl(basic_response)

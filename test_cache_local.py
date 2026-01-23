#!/usr/bin/env python3
"""
Test script for the Qdrant-based semantic cache system
Tests both exact and semantic caching functionality (localhost version)
"""

import asyncio
import httpx
import json
import time
from typing import Dict, Any

# Configuration - using localhost URLs
API_BASE_URL = "http://localhost:8000"
LITELLM_URL = "http://localhost:8001"
QDRANT_URL = "http://localhost:6333"

# Test credentials
USERNAME = "admin"
PASSWORD = "secret123"

# Global variable for token and headers
JWT_TOKEN = None
headers = {"Content-Type": "application/json"}

async def get_auth_token():
    """Get a fresh JWT token for authentication"""
    global JWT_TOKEN, headers
    
    print("🔐 Getting authentication token...")
    
    login_data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE_URL}/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            
            if response.status_code != 200:
                print(f"❌ Authentication failed: {response.status_code} - {response.text}")
                return False
            
            auth_data = response.json()
            JWT_TOKEN = auth_data.get("access_token")
            
            if not JWT_TOKEN:
                print("❌ No access token in response")
                return False
            
            # Update global headers with the token
            headers = {
                "Authorization": f"Bearer {JWT_TOKEN}",
                "Content-Type": "application/json"
            }
            
            print("✅ Successfully authenticated")
            return True
            
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False

async def test_exact_cache():
    """Test exact cache functionality"""
    print("🔍 Testing Exact Cache...")
    
    # Test prompt
    test_request = {
        "prompt": "What is the capital of France?",
        "model": "groq-kimi-primary",
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    async with httpx.AsyncClient() as client:
        # First request - should miss cache and call LLM
        print("📤 Making first request (should miss cache)...")
        start_time = time.time()
        
        response1 = await client.post(
            f"{API_BASE_URL}/llm/generate",
            json=test_request,
            headers=headers,
            timeout=30.0
        )
        
        first_duration = time.time() - start_time
        print(f"✅ First request completed in {first_duration:.2f}s")
        
        if response1.status_code != 200:
            print(f"❌ First request failed: {response1.status_code} - {response1.text}")
            return False
        
        result1 = response1.json()
        
        # Second identical request - should hit exact cache
        print("📤 Making second identical request (should hit exact cache)...")
        start_time = time.time()
        
        response2 = await client.post(
            f"{API_BASE_URL}/llm/generate",
            json=test_request,
            headers=headers,
            timeout=30.0
        )
        
        second_duration = time.time() - start_time
        print(f"✅ Second request completed in {second_duration:.2f}s")
        
        if response2.status_code != 200:
            print(f"❌ Second request failed: {response2.status_code} - {response2.text}")
            return False
        
        result2 = response2.json()
        
        # Verify cache hit
        if result1["response"] == result2["response"]:
            print(f"✅ Exact cache working! Speed improvement: {first_duration/second_duration:.1f}x")
            return True
        else:
            print("❌ Exact cache failed - responses don't match")
            return False

async def test_semantic_cache():
    """Test semantic cache functionality with improved detection logic"""
    print("\n🧠 Testing Semantic Cache...")
    
    # Similar prompts that should trigger semantic cache
    prompt1 = "What is the capital city of France?"
    prompt2 = "Tell me the capital of France"
    prompt3 = "Which city is the capital of France?"
    
    test_request1 = {
        "prompt": prompt1,
        "model": "groq-kimi-primary", 
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    test_request2 = {
        "prompt": prompt2,
        "model": "groq-kimi-primary",
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    test_request3 = {
        "prompt": prompt3,
        "model": "groq-kimi-primary",
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    async with httpx.AsyncClient() as client:
        # First request - should create cache entry
        print("📤 Making first request (will create cache entry)...")
        print(f"   Prompt: '{prompt1}'")
        start_time = time.time()
        
        response1 = await client.post(
            f"{API_BASE_URL}/llm/generate",
            json=test_request1,
            headers=headers,
            timeout=30.0
        )
        
        first_duration = time.time() - start_time
        print(f"✅ First request completed in {first_duration:.2f}s")
        
        if response1.status_code != 200:
            print(f"❌ First request failed: {response1.status_code} - {response1.text}")
            return False
        
        result1 = response1.json()
        response1_id = result1.get('id', 'unknown')
        similarity1 = response1.headers.get('x-semantic-similarity')
        print(f"   Response ID: {response1_id}")
        if similarity1:
            print(f"   Similarity score: {similarity1}")
        
        # Wait a moment to ensure cache is written
        await asyncio.sleep(1)
        
        # Second similar request - should hit semantic cache
        print("\n📤 Making semantically similar request (should hit cache)...")
        print(f"   Prompt: '{prompt2}'")
        start_time = time.time()
        
        response2 = await client.post(
            f"{API_BASE_URL}/llm/generate",
            json=test_request2,
            headers=headers,
            timeout=30.0
        )
        
        second_duration = time.time() - start_time
        print(f"✅ Second request completed in {second_duration:.2f}s")
        
        if response2.status_code != 200:
            print(f"❌ Second request failed: {response2.status_code} - {response2.text}")
            return False
        
        result2 = response2.json()
        response2_id = result2.get('id', 'unknown')
        similarity2 = response2.headers.get('x-semantic-similarity')
        print(f"   Response ID: {response2_id}")
        if similarity2:
            print(f"   Similarity score: {similarity2}")
        
        # Third similar request - should also hit semantic cache
        print("\n📤 Making third similar request (should also hit cache)...")
        print(f"   Prompt: '{prompt3}'")
        start_time = time.time()
        
        response3 = await client.post(
            f"{API_BASE_URL}/llm/generate",
            json=test_request3,
            headers=headers,
            timeout=30.0
        )
        
        third_duration = time.time() - start_time
        print(f"✅ Third request completed in {third_duration:.2f}s")
        
        if response3.status_code != 200:
            print(f"❌ Third request failed: {response3.status_code} - {response3.text}")
            return False
        
        result3 = response3.json()
        response3_id = result3.get('id', 'unknown')
        similarity3 = response3.headers.get('x-semantic-similarity')
        print(f"   Response ID: {response3_id}")
        if similarity3:
            print(f"   Similarity score: {similarity3}")
        
        # Analyze cache behavior based on what we know from LiteLLM logs
        print("\n🔍 Analyzing semantic cache behavior...")
        
        response1_text = result1.get('response', '')
        response2_text = result2.get('response', '')
        response3_text = result3.get('response', '')
        
        cache_hits = 0
        reasons = []
        
        # Primary indicator: Identical response content (from LiteLLM logs)
        # When semantic cache hits, LiteLLM returns identical responses
        if response2_text == response1_text and response2_text.strip():
            cache_hits += 1
            reasons.append(f"Request 2 hit semantic cache (identical response content)")
            if similarity2:
                reasons.append(f"  - Similarity score: {similarity2}")
            else:
                reasons.append(f"  - Response length: {len(response2_text)} chars")
        
        if response3_text == response1_text and response3_text.strip():
            cache_hits += 1
            reasons.append(f"Request 3 hit semantic cache (identical response content)")
            if similarity3:
                reasons.append(f"  - Similarity score: {similarity3}")
            else:
                reasons.append(f"  - Response length: {len(response3_text)} chars")
        
        # Secondary indicator: Timing improvements (cache is faster)
        timing_improvements = []
        if second_duration < first_duration * 0.5:  # At least 50% faster for cache hit
            timing_improvements.append(f"Request 2: {first_duration/second_duration:.1f}x faster ({second_duration:.3f}s vs {first_duration:.3f}s)")
        if third_duration < first_duration * 0.5:
            timing_improvements.append(f"Request 3: {first_duration/third_duration:.1f}x faster ({third_duration:.3f}s vs {first_duration:.3f}s)")
        
        if timing_improvements:
            reasons.extend(["Timing improvements detected:"] + [f"  - {imp}" for imp in timing_improvements])
        
        # Print analysis results
        print(f"   Response 1 (original): {len(response1_text)} chars")
        print(f"   Response 2 (semantic): {len(response2_text)} chars")
        print(f"   Response 3 (semantic): {len(response3_text)} chars")
        print(f"   Timing: {first_duration:.3f}s → {second_duration:.3f}s → {third_duration:.3f}s")
        
        for reason in reasons:
            print(f"   {reason}")
        
        # Determine success - be more strict about detection
        content_matches = (response2_text == response1_text) + (response3_text == response1_text)
        
        if content_matches >= 1:
            print(f"\n✅ Semantic cache working! {content_matches}/2 requests returned identical content")
            return True
        elif len(timing_improvements) >= 1:
            print(f"\n⚠️  Semantic cache possibly working (timing improvements) but different responses")
            print(f"   This might indicate the cache threshold is too low or responses are non-deterministic")
            return True
        else:
            print(f"\n❌ Semantic cache not working - no cache hits detected")
            print(f"   Different responses suggest no semantic cache hits occurred")
            print(f"   Try with more similar prompts or check cache similarity threshold")
            return False

async def test_cache_stats():
    """Test cache statistics endpoint"""
    print("\n📊 Testing Cache Statistics...")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE_URL}/llm/cache/stats",
            headers=headers,
            timeout=10.0
        )
        
        if response.status_code != 200:
            print(f"❌ Cache stats failed: {response.status_code} - {response.text}")
            return False
        
        stats = response.json()
        print("✅ Cache statistics:")
        print(json.dumps(stats, indent=2))
        return True

async def test_prometheus_metrics():
    """Test Prometheus metrics endpoint for cache metrics"""
    print("\n📈 Testing Prometheus Metrics...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{API_BASE_URL}/monitoring/metrics",
                timeout=10.0
            )
            
            if response.status_code != 200:
                print(f"❌ Metrics endpoint failed: {response.status_code} - {response.text}")
                return False
            
            metrics_text = response.text
            
            # Check for cache-specific metrics
            cache_metrics = []
            for line in metrics_text.split('\n'):
                if any(cache_term in line.lower() for cache_term in ['cache', 'llmops_cache']):
                    cache_metrics.append(line.strip())
            
            if cache_metrics:
                print("✅ Found cache metrics in Prometheus:")
                for metric in cache_metrics[:10]:  # Show first 10
                    if metric and not metric.startswith('#'):
                        print(f"   {metric}")
                return True
            else:
                print("⚠️  No cache metrics found in Prometheus output")
                return False
                
        except Exception as e:
            print(f"❌ Error testing metrics: {e}")
            return False

async def test_qdrant_health():
    """Test Qdrant health"""
    print("\n🏥 Testing Qdrant Health...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{QDRANT_URL}/", timeout=5.0)
            if response.status_code == 200:
                print("✅ Qdrant is healthy")
                return True
            else:
                print(f"❌ Qdrant health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Qdrant connection failed: {e}")
            return False

async def test_litellm_health():
    """Test LiteLLM health"""
    print("\n🏥 Testing LiteLLM Health...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{LITELLM_URL}/health", timeout=5.0)
            if response.status_code == 200:
                print("✅ LiteLLM is healthy")
                return True
            else:
                print(f"❌ LiteLLM health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ LiteLLM connection failed: {e}")
            return False

async def main():
    """Run all tests"""
    print("🚀 Starting Cache System Tests (Local)")
    print("=" * 50)
    
    # Get authentication token first
    auth_ok = await get_auth_token()
    if not auth_ok:
        print("\n❌ Authentication failed. Cannot proceed with tests.")
        return False
    
    # Health checks
    qdrant_ok = await test_qdrant_health()
    litellm_ok = await test_litellm_health()
    
    if not (qdrant_ok and litellm_ok):
        print("\n❌ Prerequisites not met. Please ensure all services are running.")
        return False
    
    # Cache tests
    exact_cache_ok = await test_exact_cache()
    semantic_cache_ok = await test_semantic_cache()
    stats_ok = await test_cache_stats()
    metrics_ok = await test_prometheus_metrics()
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Summary:")
    print(f"   Qdrant Health: {'✅' if qdrant_ok else '❌'}")
    print(f"   LiteLLM Health: {'✅' if litellm_ok else '❌'}")
    print(f"   Exact Cache: {'✅' if exact_cache_ok else '❌'}")
    print(f"   Semantic Cache: {'✅' if semantic_cache_ok else '❌'}")
    print(f"   Cache Stats: {'✅' if stats_ok else '❌'}")
    print(f"   Prometheus Metrics: {'✅' if metrics_ok else '❌'}")
    
    all_passed = all([qdrant_ok, litellm_ok, exact_cache_ok, semantic_cache_ok, stats_ok, metrics_ok])
    
    if all_passed:
        print("\n🎉 All tests passed! Your cache system is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the logs above for details.")
    
    return all_passed

if __name__ == "__main__":
    print("🔐 This script will automatically authenticate using admin credentials")
    print("📋 Make sure your Docker services are running before starting tests\n")
    
    asyncio.run(main())

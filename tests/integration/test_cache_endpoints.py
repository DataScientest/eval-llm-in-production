#!/usr/bin/env python3
"""
Test script for the Qdrant-based semantic cache system
Tests both exact and semantic caching functionality
"""

import asyncio
import httpx
import json
import time
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://api:8000"
LITELLM_URL = "http://litellm:4000"
QDRANT_URL = "http://qdrant:6333"

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
        "model": "groq-primary",
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
    """Test semantic cache functionality"""
    print("\n🧠 Testing Semantic Cache...")
    
    # Similar prompts that should trigger semantic cache
    prompt1 = "What is the capital city of France?"
    prompt2 = "Tell me the capital of France"
    
    test_request1 = {
        "prompt": prompt1,
        "model": "groq-primary",
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    test_request2 = {
        "prompt": prompt2,
        "model": "groq-primary",
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    async with httpx.AsyncClient() as client:
        # First request
        print("📤 Making first request...")
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
        
        # Second similar request - should hit semantic cache
        print("📤 Making semantically similar request...")
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
        
        # Check if semantic cache was used (should be faster)
        if second_duration < first_duration * 0.8:  # At least 20% faster
            print(f"✅ Semantic cache likely working! Speed improvement: {first_duration/second_duration:.1f}x")
            return True
        else:
            print(f"⚠️  Semantic cache may not have triggered (times: {first_duration:.2f}s vs {second_duration:.2f}s)")
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
    print("🚀 Starting Cache System Tests")
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
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Summary:")
    print(f"   Qdrant Health: {'✅' if qdrant_ok else '❌'}")
    print(f"   LiteLLM Health: {'✅' if litellm_ok else '❌'}")
    print(f"   Exact Cache: {'✅' if exact_cache_ok else '❌'}")
    print(f"   Semantic Cache: {'✅' if semantic_cache_ok else '❌'}")
    print(f"   Cache Stats: {'✅' if stats_ok else '❌'}")
    
    all_passed = all([qdrant_ok, litellm_ok, exact_cache_ok, semantic_cache_ok, stats_ok])
    
    if all_passed:
        print("\n🎉 All tests passed! Your cache system is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the logs above for details.")
    
    return all_passed

if __name__ == "__main__":
    print("🔐 This script will automatically authenticate using admin credentials")
    print("📋 Make sure your Docker services are running before starting tests\n")
    
    asyncio.run(main())

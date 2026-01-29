#!/usr/bin/env python3
"""
Test script for JWT authentication on the secured-generate endpoint.
This script demonstrates how to authenticate and use the secured endpoint.
"""

import requests
import json

# API Base URL
BASE_URL = "http://localhost:8000"

def test_login():
    """Test user login and token generation."""
    print("🔐 Testing user authentication...")
    
    # Test with valid credentials
    login_data = {
        "username": "admin",
        "password": "secret123"
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    
    if response.status_code == 200:
        token_data = response.json()
        print("✅ Login successful!")
        print(f"   Token type: {token_data['token_type']}")
        print(f"   Expires in: {token_data['expires_in']} seconds")
        print(f"   User: {token_data['user']['username']} ({token_data['user']['role']})")
        return token_data['access_token']
    else:
        print(f"❌ Login failed: {response.status_code} - {response.text}")
        return None

def test_invalid_login():
    """Test login with invalid credentials."""
    print("\n🔐 Testing invalid authentication...")
    
    login_data = {
        "username": "admin",
        "password": "wrongpassword"
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    
    if response.status_code == 401:
        print("✅ Invalid credentials properly rejected!")
    else:
        print(f"❌ Expected 401, got: {response.status_code}")

def test_secured_endpoint_without_token():
    """Test secured endpoint without authentication."""
    print("\n🔒 Testing secured endpoint without token...")
    
    prompt_data = {
        "prompt": "Hello, how are you?",
        "max_tokens": 50
    }
    
    response = requests.post(f"{BASE_URL}/secured-generate", json=prompt_data)
    
    if response.status_code == 403:
        print("✅ Secured endpoint properly rejected unauthenticated request!")
    else:
        print(f"❌ Expected 403, got: {response.status_code} - {response.text}")

def test_secured_endpoint_with_token(token):
    """Test secured endpoint with valid JWT token."""
    print("\n🔓 Testing secured endpoint with valid token...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    prompt_data = {
        "prompt": "Hello, how are you? Please respond briefly.",
        "max_tokens": 50,
        "temperature": 0.7
    }
    
    response = requests.post(f"{BASE_URL}/secured-generate", json=prompt_data, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Secured endpoint accessible with valid token!")
        print(f"   Model: {result['model']}")
        print(f"   Response: {result['response'][:100]}...")
        print(f"   Tokens: {result['prompt_tokens']} + {result['completion_tokens']} = {result['total_tokens']}")
        print(f"   Cost: ${result['cost']:.6f}")
        print(f"   Security status: {result['security_status']}")
    else:
        print(f"❌ Secured endpoint failed: {response.status_code} - {response.text}")

def test_secured_endpoint_with_invalid_token():
    """Test secured endpoint with invalid JWT token."""
    print("\n🔒 Testing secured endpoint with invalid token...")
    
    headers = {
        "Authorization": "Bearer invalid.token.here",
        "Content-Type": "application/json"
    }
    
    prompt_data = {
        "prompt": "Hello, how are you?",
        "max_tokens": 50
    }
    
    response = requests.post(f"{BASE_URL}/secured-generate", json=prompt_data, headers=headers)
    
    if response.status_code == 401:
        print("✅ Invalid token properly rejected!")
    else:
        print(f"❌ Expected 401, got: {response.status_code} - {response.text}")

def test_user_info(token):
    """Test getting current user information."""
    print("\n👤 Testing user info endpoint...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    
    if response.status_code == 200:
        user_info = response.json()
        print("✅ User info retrieved successfully!")
        print(f"   Username: {user_info['username']}")
        print(f"   Role: {user_info['role']}")
    else:
        print(f"❌ User info failed: {response.status_code} - {response.text}")

def compare_endpoints(token):
    """Compare regular vs secured endpoint."""
    print("\n🔄 Comparing regular vs secured endpoints...")
    
    prompt_data = {
        "prompt": "What is 2+2?",
        "max_tokens": 30
    }
    
    # Test regular endpoint
    print("   Regular endpoint:")
    response1 = requests.post(f"{BASE_URL}/generate", json=prompt_data)
    if response1.status_code == 200:
        result1 = response1.json()
        print(f"   ✅ Response: {result1['response']}")
    else:
        print(f"   ❌ Failed: {response1.status_code}")
    
    # Test secured endpoint
    print("   Secured endpoint:")
    headers = {"Authorization": f"Bearer {token}"}
    response2 = requests.post(f"{BASE_URL}/secured-generate", json=prompt_data, headers=headers)
    if response2.status_code == 200:
        result2 = response2.json()
        print(f"   ✅ Response: {result2['response']}")
    else:
        print(f"   ❌ Failed: {response2.status_code}")

def main():
    """Run all JWT authentication tests."""
    print("🚀 JWT Authentication Test Suite")
    print("=" * 50)
    
    # Test 1: Valid login
    token = test_login()
    
    # Test 2: Invalid login
    test_invalid_login()
    
    # Test 3: Secured endpoint without token
    test_secured_endpoint_without_token()
    
    # Test 4: Secured endpoint with invalid token
    test_secured_endpoint_with_invalid_token()
    
    if token:
        # Test 5: Secured endpoint with valid token
        test_secured_endpoint_with_token(token)
        
        # Test 6: User info
        test_user_info(token)
        
        # Test 7: Compare endpoints
        compare_endpoints(token)
    
    print("\n" + "=" * 50)
    print("🎉 JWT Authentication tests completed!")
    print("\n📋 Available credentials for testing:")
    print("   Username: admin, Password: secret123 (role: admin)")
    print("   Username: user, Password: password123 (role: user)")
    print("\n📖 Usage example:")
    print("   1. POST /auth/login with username/password")
    print("   2. Use returned token in Authorization: Bearer <token>")
    print("   3. Access /secured-generate with token")

if __name__ == "__main__":
    main()
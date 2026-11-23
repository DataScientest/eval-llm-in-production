#!/bin/bash

echo "🔍 Cache Test with Log Verification"
echo "==================================="

# Get token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "secret123"}' \
    | jq -r '.access_token')

if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
    echo "❌ Authentication failed"
    exit 1
fi

echo "🔐 Authentication successful"

# Helper function to check logs
check_logs() {
    local search_term="$1"
    local description="$2"
    echo -n "📋 Checking logs for $description: "
    if docker logs llmops-setup-course-api-1 --tail=10 | grep -q "$search_term"; then
        echo "✅ Found"
    else
        echo "❌ Not found"
    fi
}

echo ""
echo "🎯 Test 1: Exact Cache Demo"
echo "============================"

# Clear previous logs by getting current log count
INITIAL_LOGS=$(docker logs llmops-setup-course-api-1 2>&1 | wc -l)

echo "🔍 Making first call (should create cache entry)..."
RESPONSE1=$(curl -s -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-primary", "prompt": "What is Docker?", "max_tokens": 200}')

echo "Response: $(echo $RESPONSE1 | jq -r '.response' | head -c 50)..."

sleep 2

echo ""
echo "🎯 Making second identical call (should hit exact cache)..."
RESPONSE2=$(curl -s -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-primary", "prompt": "What is Docker?", "max_tokens": 200}')

echo "Response: $(echo $RESPONSE2 | jq -r '.response' | head -c 50)..."

# Check for exact cache hit in logs
echo ""
echo "📊 Log Analysis:"
check_logs "DEBUG: Exact cache hit!" "Exact Cache Hit"

echo ""
echo "🧠 Test 2: Semantic Cache Demo"
echo "==============================="

echo "🔍 Making first semantic call..."
RESPONSE3=$(curl -s -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-primary", "prompt": "How does containerization technology work?", "max_tokens": 200}')

echo "Response: $(echo $RESPONSE3 | jq -r '.response' | head -c 50)..."

sleep 3

echo ""
echo "🎯 Making semantically similar call..."
RESPONSE4=$(curl -s -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-primary", "prompt": "Explain container virtualization concepts", "max_tokens": 200}')

echo "Response: $(echo $RESPONSE4 | jq -r '.response' | head -c 50)..."

# Check for semantic cache hit in logs
echo ""
echo "📊 Log Analysis:"
check_logs "DEBUG: Semantic cache hit with similarity" "Semantic Cache Hit"

echo ""
echo "🔍 Recent API Logs (last 15 lines):"
echo "======================================"
docker logs llmops-setup-course-api-1 --tail=15 | grep -E "(DEBUG: |INFO: )"

echo ""
echo "✅ Cache demonstration completed!"
echo ""
echo "💡 Summary:"
echo "   • Exact Cache: Matches identical prompts (hash-based)"
echo "   • Semantic Cache: Matches similar meaning (embedding-based)"
echo "   • Both caches provide significant performance improvements"

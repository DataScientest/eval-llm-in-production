#!/bin/bash

echo "🚀 Cache Performance Benchmark"
echo "=============================="

# Get token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "secret123"}' \
    | jq -r '.access_token')

if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
    echo "❌ Authentication failed"
    exit 1
fi

echo "🔐 Token obtained: ${TOKEN:0:20}..."

# Clear cache before test
echo ""
echo "🧹 Clearing cache for clean benchmark..."
curl -s -X DELETE "http://localhost:8000/llm/cache/clear" \
    -H "Authorization: Bearer $TOKEN" > /dev/null

echo ""
echo "📊 Performance Test 1: Exact Cache"
echo "=================================="

# First call - no cache
echo -n "⏱️  First call (no cache): "
TIME1=$(curl -s -w "%{time_total}" -o /tmp/response1.json \
    -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-primary", "prompt": "What is machine learning?", "max_tokens": 200}')
echo "${TIME1}s"

sleep 2  # Allow cache to write

# Second call - exact cache
echo -n "⚡ Second call (exact cache): "
TIME2=$(curl -s -w "%{time_total}" -o /tmp/response2.json \
    -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-primary", "prompt": "What is machine learning?", "max_tokens": 200}')
echo "${TIME2}s"

# Calculate improvement
IMPROVEMENT=$(echo "scale=2; ($TIME1 - $TIME2) / $TIME1 * 100" | bc -l)
echo "📈 Speed improvement: ${IMPROVEMENT}%"

echo ""
echo "📊 Performance Test 2: Semantic Cache"
echo "====================================="

# First call - new prompt
echo -n "⏱️  First call (no cache): "
TIME3=$(curl -s -w "%{time_total}" -o /tmp/response3.json \
    -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-primary", "prompt": "Explain artificial intelligence concepts", "max_tokens": 200}')
echo "${TIME3}s"

sleep 3  # Allow semantic cache to index

# Second call - semantically similar
echo -n "⚡ Similar call (semantic cache): "
TIME4=$(curl -s -w "%{time_total}" -o /tmp/response4.json \
    -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-primary", "prompt": "What are the fundamentals of AI?", "max_tokens": 200}')
echo "${TIME4}s"

# Calculate improvement for semantic
SEMANTIC_IMPROVEMENT=$(echo "scale=2; ($TIME3 - $TIME4) / $TIME3 * 100" | bc -l)
echo "📈 Speed improvement: ${SEMANTIC_IMPROVEMENT}%"

echo ""
echo "🏆 Cache Performance Summary"
echo "============================"
printf "Exact Cache:     %.3fs → %.3fs (%.1f%% faster)\n" $TIME1 $TIME2 $IMPROVEMENT
printf "Semantic Cache:  %.3fs → %.3fs (%.1f%% faster)\n" $TIME3 $TIME4 $SEMANTIC_IMPROVEMENT

# Clean up temp files
rm -f /tmp/response*.json

echo ""
echo "✅ Performance benchmark completed!"

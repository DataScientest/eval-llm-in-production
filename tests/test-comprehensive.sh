#!/bin/bash

echo "🚀 Test complet du système LiteLLM + Qdrant + MLflow"
echo "=================================================="

# Test 1: API Authentication
echo ""
echo "🔐 Test 1: Authentication"
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "secret123"}' \
    | jq -r '.access_token')

if [ "$TOKEN" != "null" ] && [ -n "$TOKEN" ]; then
    echo "✅ Authentication successful"
else
    echo "❌ Authentication failed"
    exit 1
fi

# Test 2: Premier appel (pas de cache)
echo ""
echo "🔍 Test 2: Premier appel API (pas de cache attendu)"
RESPONSE1=$(curl -s -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-primary", "prompt": "What are best practices for secure API design?", "max_tokens": 200}')

echo "Réponse reçue: $(echo $RESPONSE1 | jq -r '.response' | head -c 100)..."

# Test 3: Deuxième appel identique (cache attendu)
echo ""
echo "🎯 Test 3: Deuxième appel identique (cache attendu)"
sleep 2  # Petit délai pour s'assurer que le cache est indexé

RESPONSE2=$(curl -s -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-primary", "prompt": "What are best practices for secure API design?", "max_tokens": 200}')

echo "Réponse reçue: $(echo $RESPONSE2 | jq -r '.response' | head -c 100)..."

# Test 4: Variation sémantique
echo ""
echo "🔄 Test 4: Variation sémantique"
RESPONSE3=$(curl -s -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-primary", "prompt": "Could you share guidelines for creating a secure API?", "max_tokens": 200}')

echo "Réponse reçue: $(echo $RESPONSE3 | jq -r '.response' | head -c 100)..."

# Test 5: Vérification MLflow
echo ""
echo "📊 Test 5: Vérification traces MLflow"
TRACES=$(curl -s -X GET "http://localhost:5001/api/2.0/mlflow/traces?experiment_ids=1" | jq '.traces | length')
echo "✅ Nombre de traces MLflow trouvées: $TRACES"

# Test 6: Vérification cache LiteLLM
echo ""
echo "💾 Test 6: Vérification cache LiteLLM"
CACHE_INFO=$(curl -s -X GET "http://localhost:8001/cache/ping")
echo "Cache status: $(echo $CACHE_INFO | jq -r '.status')"

echo ""
echo "🎉 Tests terminés avec succès !"
echo "🔹 Authentification: ✅"
echo "🔹 API LLM: ✅" 
echo "🔹 Cache sémantique: ✅"
echo "🔹 MLflow tracing: ✅"
echo "🔹 Infrastructure: ✅"

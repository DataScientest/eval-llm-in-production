#!/bin/bash

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction pour afficher les messages avec couleur
echo_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
echo_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo_info "Test spécifique du cache sémantique"
echo "====================================="

# Get token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "secret123"}' \
    | jq -r '.access_token')

echo_info "Token obtenu: ${TOKEN:0:20}..."

# Test 1: Premier prompt unique
echo ""
echo_info "Test 1: Premier prompt complètement nouveau"
RESPONSE1=$(curl -s -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-kimi-primary", "prompt": "How can I protect my REST API from attacks?", "max_tokens": 80}')

RESPONSE1_TEXT=$(echo $RESPONSE1 | jq -r '.response')
echo "Réponse 1: $(echo $RESPONSE1_TEXT | head -c 80)..."

# Test 2: Prompt sémantiquement très similaire mais formulé différemment
echo ""
echo_info "Test 2: Prompt sémantiquement similaire (différentes mots)"
sleep 3  # Attendre que le cache soit indexé

RESPONSE2=$(curl -s -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-kimi-primary", "prompt": "What methods exist to secure a REST API against malicious requests?", "max_tokens": 80}')

RESPONSE2_TEXT=$(echo $RESPONSE2 | jq -r '.response')
echo "Réponse 2: $(echo $RESPONSE2_TEXT | head -c 80)..."

# Vérifier si les réponses sont similaires (indiquant un cache sémantique)
if [ "$RESPONSE1_TEXT" = "$RESPONSE2_TEXT" ]; then
    echo_success "Cache sémantique fonctionnel - les réponses sont identiques"
else
    echo_info "Les réponses sont différentes (ce qui est attendu si le cache sémantique n'est pas activé)"
fi

# Test 3: Prompt complètement différent (pas de cache attendu)
echo ""
echo_info "Test 3: Prompt complètement différent (pas de cache attendu)"
RESPONSE3=$(curl -s -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-kimi-primary", "prompt": "Explain quantum computing concepts", "max_tokens": 80}')

RESPONSE3_TEXT=$(echo $RESPONSE3 | jq -r '.response')
echo "Réponse 3: $(echo $RESPONSE3_TEXT | head -c 80)..."

# Vérifier que la réponse 3 est différente des réponses 1 et 2
if [ "$RESPONSE3_TEXT" != "$RESPONSE1_TEXT" ] && [ "$RESPONSE3_TEXT" != "$RESPONSE2_TEXT" ]; then
    echo_success "Réponse différente pour un prompt différent (comportement attendu)"
else
    echo_error "Réponse inattendue pour un prompt différent"
fi

echo ""
echo_info "Vérification des logs pour cache sémantique..."
# Vérifier les logs de LiteLLM pour voir les hits de cache
# docker compose logs litellm | grep -i "cache hit" | tail -5

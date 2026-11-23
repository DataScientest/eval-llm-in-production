#!/usr/bin/env bash
# Checks one exam exercise against the running stack.
# Usage: bash scripts/check_exercise.sh <1-6>
#   1-3: required exercises    4-6: bonus exercises
# Requirements: bash, curl, jq, docker compose. Start the stack first: docker compose up -d
set -u

API_URL="${API_URL:-http://localhost:8000}"
ADMIN_PASSWORD="${AUTH_ADMIN_PASSWORD:-secret123}"
SECURE_SECRET="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
FAILED=0

ok()   { echo "  [OK]   $1"; }
ko()   { echo "  [FAIL] $1"; FAILED=1; }
hint() { echo "         -> $1"; }

token() {
  curl -s -X POST "$API_URL/auth/login" -H "Content-Type: application/json" \
    -d "{\"username\": \"admin\", \"password\": \"$ADMIN_PASSWORD\"}" | jq -r '.access_token // empty'
}

wait_api() {
  for _ in $(seq 1 30); do
    curl -fs -o /dev/null "$API_URL/system/health" 2>/dev/null && return 0
    sleep 2
  done
  return 1
}

api_logs_since() { docker compose logs --no-log-prefix --since "$1" api 2>/dev/null; }

check_1() {
  echo "Exercise 1 - Secure configuration"
  if docker compose run --rm --no-deps -e JWT_SECRET_KEY=your-secret-key-change-in-production api \
      python -c "from config.settings import settings" >/dev/null 2>&1; then
    ko "the API loads its settings with the default JWT_SECRET_KEY"
    hint "settings must refuse insecure or short secrets (fail fast at startup)"
  else
    ok "default JWT_SECRET_KEY is rejected at startup"
  fi
  if docker compose run --rm --no-deps -e JWT_SECRET_KEY="$SECURE_SECRET" api \
      python -c "from config.settings import settings" >/dev/null 2>&1; then
    ok "a secure JWT_SECRET_KEY (64 hex characters) is accepted"
  else
    ko "the settings also reject a secure JWT_SECRET_KEY"
  fi
  origins=$(docker compose run --rm --no-deps -e JWT_SECRET_KEY="$SECURE_SECRET" api \
      python -c "from config.settings import settings; print(list(settings.CORS_ORIGINS))" 2>/dev/null | tail -1)
  if [ -n "$origins" ] && ! echo "$origins" | grep -q "\*"; then
    ok "CORS_ORIGINS is an explicit list: $origins"
  else
    ko "CORS_ORIGINS still allows every origin (\"*\") or cannot be read: $origins"
  fi
}

check_2() {
  echo "Exercise 2 - Error handling and retry"
  TOKEN=$(token)
  body=$(curl -s -X POST "$API_URL/llm/generate" -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" -d '{"model": "groq-doesnotexist", "prompt": "hi", "max_tokens": 20}')
  if echo "$body" | jq -e '(.detail // .) | has("incident_id") and has("timestamp")' >/dev/null 2>&1; then
    ok "error responses carry incident_id and timestamp"
  else
    ko "error response has no incident_id/timestamp: $(echo "$body" | head -c 120)"
    hint "return a structured error: error type, message, incident_id, timestamp"
  fi
  docker compose stop litellm >/dev/null 2>&1
  start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  curl -s -m 90 -o /dev/null -X POST "$API_URL/llm/generate" -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" -d '{"model": "groq-primary", "prompt": "retry test", "max_tokens": 20}'
  docker compose start litellm >/dev/null 2>&1
  if api_logs_since "$start" | grep -qi -E "attempt [0-9]"; then
    ok "retries are logged while LiteLLM is down"
  else
    ko "no retry attempt found in the API logs while LiteLLM was down"
    hint "log each attempt, for example: Attempt 1/4 failed: APIConnectionError. Retrying in 1.1s"
  fi
}

check_3() {
  echo "Exercise 3 - Structured logging"
  rid=$(curl -s -D - -o /dev/null "$API_URL/system/health" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-request-id"{print $2}')
  if [ -n "$rid" ]; then ok "responses carry an X-Request-ID header ($rid)"; else ko "no X-Request-ID header in responses"; fi
  sleep 1
  logs=$(docker compose logs --no-log-prefix --tail 200 api 2>/dev/null)
  json_lines=$(echo "$logs" | jq -R -c 'fromjson? | select(type == "object" and has("level") and has("message"))' 2>/dev/null | wc -l | tr -d ' ')
  if [ "$json_lines" -gt 0 ]; then ok "the API writes JSON logs ($json_lines JSON lines in the last 200)"; else
    ko "no JSON log line with level and message in the API logs"; hint "configure a JSON formatter and replace print() with logger calls"; fi
  if [ -n "$rid" ] && echo "$logs" | jq -R -c 'fromjson?' 2>/dev/null | grep -q "$rid"; then
    ok "the request_id appears in the logs of that request"
  else
    ko "the X-Request-ID value is not found in the logs"
  fi
}

check_4() {
  echo "Exercise 4 (bonus) - Graceful shutdown"
  start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  docker compose stop api >/dev/null 2>&1
  logs=$(api_logs_since "$start")
  docker compose start api >/dev/null 2>&1
  if echo "$logs" | grep -qi -E "waiting for .*request"; then ok "shutdown waits for in-flight requests"; else
    ko "no 'waiting for ... requests' message on shutdown"; fi
  if echo "$logs" | grep -qi -E "clos(e|ing).*(qdrant|connection)|cleanup"; then ok "resources are closed on shutdown"; else
    ko "no resource cleanup message on shutdown"; fi
  wait_api || ko "the API did not come back after restart"
}

check_5() {
  echo "Exercise 5 (bonus) - Timeouts and request limits"
  TOKEN=$(token)
  code=$(head -c 2000000 /dev/zero | tr '\0' 'a' | curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/llm/generate" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" --data-binary @-)
  if [ "$code" = "413" ]; then ok "a 2 MB body is rejected with 413"; else ko "a 2 MB body returns $code instead of 413"; fi
  # The OpenAI client that calls LiteLLM must be created with a timeout.
  if grep -rhs -A8 -E "(Async)?OpenAI\(" src/api 2>/dev/null | grep -q -E "timeout\s*="; then
    ok "the OpenAI client calling LiteLLM has a timeout"
  else
    ko "the OpenAI client calling LiteLLM is created without timeout"
    hint "openai.OpenAI(..., timeout=httpx.Timeout(30.0, connect=5.0))"
  fi
}

check_6() {
  echo "Exercise 6 (bonus) - Health checks"
  code=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health")
  if [ "$code" = "200" ]; then ok "/health answers 200"; else ko "/health answers $code"; fi
  docker compose stop qdrant >/dev/null 2>&1
  sleep 35   # health results may be cached for 30 s
  body=$(curl -s -w "\n%{http_code}" "$API_URL/health/detailed")
  docker compose start qdrant >/dev/null 2>&1
  code=$(echo "$body" | tail -1)
  if [ "$code" = "503" ]; then ok "/health/detailed answers 503 when Qdrant is down"; else
    ko "/health/detailed answers $code when Qdrant is down (expected 503)"; fi
  if echo "$body" | grep -q '"degraded"'; then
    ok "status is degraded"; else ko "status is not degraded"; fi
}

case "${1:-}" in
  1|2|3|4|5|6) "check_$1" ;;
  *) echo "Usage: bash scripts/check_exercise.sh <1-6>"; exit 2 ;;
esac
echo
if [ "$FAILED" = 0 ]; then echo "Exercise $1: PASSED"; else echo "Exercise $1: NOT PASSED"; fi
exit "$FAILED"

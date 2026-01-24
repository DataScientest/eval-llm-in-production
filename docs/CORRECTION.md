# LLMOps Exam - Correction Guide

This document explains the implementation of the 6 production readiness fixes.

---

## Exercise 1: Secure Configuration (15 pts)

**Problem**: Insecure defaults and no validation
- `JWT_SECRET_KEY` had a default value visible in code
- `CORS_ORIGINS: ["*"]` allowed all origins
- No fail-fast on missing configuration

**Solution**:

```python
# src/api/config/settings.py
class Settings(BaseSettings):
    JWT_SECRET_KEY: str = Field(..., description="Required, no default")
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    @field_validator('JWT_SECRET_KEY')
    def validate_jwt_secret(cls, v):
        if v in INSECURE_DEFAULTS or len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be secure")
        return v
```

**Files**: `settings.py`, `env_validator.py`, `.env.example`

**Verification**:
```bash
unset JWT_SECRET_KEY && docker compose up api
# Should fail with: "JWT_SECRET_KEY must be set"
```

---

## Exercise 2: Graceful Shutdown (15 pts)

**Problem**: No resource cleanup on shutdown
- Connections leaked on restart
- In-flight requests interrupted
- MLflow traces incomplete

**Solution**:

```python
# src/api/config/lifespan.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await mlflow_service.setup_experiment()
    yield
    # Shutdown
    trigger_shutdown()
    await wait_for_active_requests(timeout=30)
    await cleanup_resources()  # Close Qdrant, finalize MLflow
```

**Files**: `lifespan.py`, `middleware/shutdown.py`

**Verification**:
```bash
curl -X POST localhost:8000/llm/generate -d '{...}' &
docker compose stop api
# Logs: "Waiting for 1 active request(s)... Graceful shutdown completed"
```

---

## Exercise 3: Request Timeouts (15 pts)

**Problem**: No timeouts, vulnerable to slow clients
- OpenAI client waited indefinitely
- No body size limits
- No circuit breaker

**Solution**:

```python
# src/api/routers/llm.py
client = openai.OpenAI(
    timeout=httpx.Timeout(30.0, connect=5.0),
    max_retries=0,
)

# Circuit breaker opens after 5 failures
if not await litellm_circuit.can_execute():
    raise HTTPException(503, "Circuit breaker open")
```

**Files**: `llm.py`, `circuit_breaker.py`, `request_limits.py`

**Verification**:
```bash
docker compose stop litellm
time curl -X POST localhost:8000/llm/generate -d '{...}'
# Returns 504 after ~30s (not infinite)
```

---

## Exercise 4: Error Handling & Retry (20 pts)

**Problem**: Generic exceptions, no retry, silent failures
- `except Exception: raise HTTPException(500, "Failed")`
- No retry on transient errors
- MLflow failures lost data silently

**Solution**:

```python
# src/api/routers/llm.py
async def call_llm_with_retry(params):
    for attempt in range(MAX_RETRIES + 1):
        try:
            return await client.chat.completions.create(**params)
        except RETRYABLE_ERRORS as e:
            delay = calculate_backoff_delay(attempt)  # 1s, 2s, 4s
            await asyncio.sleep(delay)

# Granular error handling
except openai.RateLimitError: raise HTTPException(429, {...})
except openai.BadRequestError: raise HTTPException(400, {...})
except openai.NotFoundError: raise HTTPException(404, {"model": model})
```

**Files**: `llm.py`, `utils/retry.py`

**Verification**:
```bash
# Logs show: "Attempt 1 failed. Retrying in 1.2s..."
# Error responses include: incident_id, timestamp, context
```

---

## Exercise 5: Health Checks (15 pts)

**Problem**: Fake health check always returned "healthy"
- Dependencies not checked
- Load balancer sent traffic to broken instances

**Solution**:

```python
# src/api/routers/system.py
@router.get("/health")
async def health():
    return {"status": "alive"}  # Always 200 if app runs

@router.get("/health/detailed")
async def detailed_health():
    results = await health_checker.check_all()  # Qdrant, LiteLLM, MLflow, TEI
    all_healthy = all(r.healthy for r in results.values())
    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={"status": "healthy" if all_healthy else "degraded", "checks": {...}}
    )
```

**Files**: `system.py`, `health_checker.py`, `app.py`

**Verification**:
```bash
docker compose stop qdrant
curl localhost:8000/health          # 200 {"status": "alive"}
curl localhost:8000/health/detailed # 503 {"qdrant": false, ...}
```

---

## Exercise 6: Structured Logging (20 pts)

**Problem**: Print statements, no tracing
- `print(f"DEBUG: ...")` everywhere
- No request correlation
- Logs not parseable by tools

**Solution**:

```python
# src/api/config/logging_config.py
class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        })

# src/api/middleware/request_id.py
async def request_id_middleware(request, call_next):
    request_id = f"req_{uuid.uuid4().hex[:16]}"
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

**Files**: `logging_config.py`, `request_id.py`, all files updated (replaced `print()` with `logger.*`)

**Verification**:
```bash
docker compose logs api | head -1 | jq
# {"timestamp": "...", "level": "INFO", "request_id": "req_abc123", ...}

curl -D - localhost:8000/health
# X-Request-ID: req_abc123
```

---

## File Summary

| Exercise | New Files | Modified Files |
|----------|-----------|----------------|
| 1 | `env_validator.py`, `.env.example` | `settings.py` |
| 2 | `middleware/shutdown.py` | `lifespan.py` |
| 3 | `circuit_breaker.py`, `request_limits.py` | `llm.py`, `app.py` |
| 4 | `utils/retry.py` | `llm.py` |
| 5 | `health_checker.py` | `system.py`, `app.py` |
| 6 | `logging_config.py`, `request_id.py` | All files with `print()` |

---

## Quick Verification Commands

```bash
# Ex 1: Config validation
docker compose up api  # Should fail without JWT_SECRET_KEY

# Ex 2: Graceful shutdown
docker compose restart api  # Check logs for cleanup messages

# Ex 3: Timeouts
docker compose stop litellm && curl localhost:8000/llm/generate  # 504 after 30s

# Ex 5: Health checks
docker compose stop qdrant && curl localhost:8000/health/detailed  # 503

# Ex 6: Structured logs
docker compose logs api | jq .  # Valid JSON output
```

---

## Grading Diff

To grade a student submission:

```bash
git clone <student-repo> student-solution
cd student-solution
git remote add reference <this-repo>
git fetch reference main

# See all changes
git diff reference/main..HEAD

# See changed files only
git diff --name-only reference/main..HEAD
```

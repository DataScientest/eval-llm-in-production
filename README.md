# LLMOps Production Readiness - Exam

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)

An **LLMOps exam** covering configuration management, graceful shutdown, fault tolerance, error handling, health checks, and structured logging.


### 6 Exercises

The detailed exam instructions are available in the [EXAM.md](docs/EXAM.md) file.

| # | Topic | Key Concepts |
|---|-------|--------------|
| 1 | Secure Configuration | Pydantic BaseSettings, environment validation |
| 2 | Graceful Shutdown | In-flight request tracking, resource cleanup |
| 3 | Request Timeouts | httpx timeouts, circuit breaker pattern |
| 4 | Error Handling & Retry | Granular exceptions, exponential backoff |
| 5 | Health Checks | Liveness vs readiness, dependency verification |
| 6 | Structured Logging | JSON logging, request ID tracing |


## Quick Start

Mise can be used to launch the stack and run tests but it is not required.

### Prerequisites

- Docker & Docker Compose
- curl and jq (for testing)
- [mise](https://mise.jdx.dev/) (optional, for automated testing)
- API Keys: `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`

### Launch Stack

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your API keys (JWT_SECRET_KEY is required)

# 2. Launch services (choose one)
docker compose up -d --build   # standard
mise run up                    # with mise

# 3. Verify deployment
mise run status                # with mise
make -f Makefile.curl status   # alternative
```

### Access Points

| Service | URL |
|---------|-----|
| API Docs | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |
| MLflow UI | http://localhost:5001 |
| Qdrant Dashboard | http://localhost:6333/dashboard |
| LiteLLM UI | http://localhost:8001 |


## Testing the Exercises

### Automated Testing with mise

```bash
# Install mise: https://mise.jdx.dev/getting-started.html

# Run all exercise tests
mise run test:all

# Run individual exercise tests
mise run test:ex1    # Secure Configuration
mise run test:ex2    # Graceful Shutdown
mise run test:ex3    # Request Timeouts & Circuit Breaker
mise run test:ex4    # Error Handling & Retry
mise run test:ex5    # Health Checks
mise run test:ex6    # Structured Logging

# Other useful commands
mise run status      # Check all services
mise run logs        # View API logs
mise run token       # Get JWT token
```

### Manual Testing

#### Get Authentication Token

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret123"}' \
  | jq -r '.access_token')
```

#### Exercise 1: Secure Configuration

```bash
# Missing JWT_SECRET_KEY should fail at startup
unset JWT_SECRET_KEY && docker compose up api
# Expected: ValidationError with clear message

# Check settings validation
docker compose logs api | grep -i "configuration\|settings"
```

### Exercise 2: Graceful Shutdown

```bash
# Start a long request then send SIGTERM
curl -X POST http://localhost:8000/llm/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "groq-kimi-primary", "prompt": "Write a long essay"}' &

docker compose stop api
# Expected: Request completes before shutdown (30s grace period)
```

### Exercise 3: Request Timeouts & Circuit Breaker

```bash
# Check circuit breaker status
curl -s http://localhost:8000/health/detailed \
  -H "Authorization: Bearer $TOKEN" | jq '.checks.circuit_breaker'

# After multiple failures, circuit opens
# Expected: 503 Service Unavailable with "Circuit breaker is open"
```

### Exercise 4: Error Handling & Retry

```bash
# Test with invalid model (should not retry)
curl -X POST http://localhost:8000/llm/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "invalid-model", "prompt": "test"}'
# Expected: 400 Bad Request (no retry)

# Check logs for retry attempts on transient errors
docker compose logs api | grep -i "retry\|attempt"
```

### Exercise 5: Health Checks

```bash
# Liveness probe (simple)
curl -s http://localhost:8000/health | jq
# Expected: {"status": "healthy"}

# Readiness probe (detailed)
curl -s http://localhost:8000/health/detailed \
  -H "Authorization: Bearer $TOKEN" | jq
# Expected: All dependencies checked (qdrant, litellm, mlflow)
```

### Exercise 6: Structured Logging

```bash
# Check JSON log format
docker compose logs api --tail=50 | head -20
# Expected: JSON lines with timestamp, level, request_id, message

# Verify request ID propagation
curl -X POST http://localhost:8000/llm/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: test-request-123" \
  -d '{"model": "groq-kimi-primary", "prompt": "Hello"}'

docker compose logs api | grep "test-request-123"
# Expected: All logs for this request share the same request_id
```


## Project Structure

```sh
├── EXAM.md                         # Student instructions
├── CORRECTION.md                   # Grading guide (main branch only)
├── .env.example                    # Environment template
├── docker-compose.yml              # Service orchestration
├── Makefile.curl                   # Test automation
│
├── src/api/
│   ├── main.py                     # API entry point
│   ├── config/
│   │   ├── settings.py             # Ex1: Pydantic BaseSettings
│   │   ├── env_validator.py        # Ex1: Startup validation
│   │   ├── lifespan.py             # Ex2: Graceful shutdown
│   │   ├── logging_config.py       # Ex6: JSON logging
│   │   └── app.py                  # Health endpoints
│   ├── middleware/
│   │   ├── shutdown.py             # Ex2: In-flight tracking
│   │   ├── request_limits.py       # Ex3: Body size limits
│   │   └── request_id.py           # Ex6: Request ID generation
│   ├── routers/
│   │   ├── llm.py                  # Ex3/Ex4: Timeouts, retry, errors
│   │   └── system.py               # Ex5: Health endpoints
│   ├── services/
│   │   ├── circuit_breaker.py      # Ex3: Circuit breaker pattern
│   │   └── health_checker.py       # Ex5: Dependency verification
│   └── utils/
│       └── retry.py                # Ex4: Exponential backoff
│
├── litellm/                        # LiteLLM configuration
└── tests/                          # Test suite
```


## Architecture

```sh
┌─────────────────────────────────────────────────────────────────┐
│                         Client Request                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Middleware Stack                                               │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐   │
│  │ Request ID    │→ │ Shutdown      │→ │ Request Limits    │   │
│  │ (Ex6)         │  │ Check (Ex2)   │  │ (Ex3: 1MB max)    │   │
│  └───────────────┘  └───────────────┘  └───────────────────┘   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Application                                            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Settings (Ex1)     │ Health Checks (Ex5)                  │  │
│  │ - Pydantic config  │ - /health (liveness)                 │  │
│  │ - JWT validation   │ - /health/detailed (readiness)       │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ LLM Router (Ex3, Ex4)                                     │  │
│  │ - Timeouts (30s request, 5s connect)                      │  │
│  │ - Circuit Breaker (5 failures → open)                     │  │
│  │ - Retry with exponential backoff                          │  │
│  │ - Granular error handling                                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Structured Logging (Ex6)                                  │  │
│  │ - JSON format with timestamp, level, request_id          │  │
│  │ - Contextual logging throughout request lifecycle         │  │
│  └───────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  External Services                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │ LiteLLM    │  │ Qdrant     │  │ MLflow     │                │
│  │ :8001      │  │ :6333      │  │ :5001      │                │
│  └────────────┘  └────────────┘  └────────────┘                │
└─────────────────────────────────────────────────────────────────┘
```


## Maintenance Commands

```bash
# Rebuild services
docker compose down && docker compose up -d --build

# View logs with JSON parsing
docker compose logs api | jq -R 'fromjson? // .'

# Check all health endpoints
curl -s http://localhost:8000/health && echo
curl -s http://localhost:8000/health/detailed -H "Authorization: Bearer $TOKEN" | jq

# Clean up volumes (destroys data)
docker compose down -v
```


## Grading

### Validation Thresholds
- **Minimum 60 points (60%)** to pass
- **80 points (80%)** for distinction
- **90 points (90%)** for excellence

### Validation Rules
- **Core exercises required**: At least 2 of [Ex1, Ex2, Ex6] must be complete
- **Partial credit**: 50% points for functional but incomplete implementations
- **Bonus**: +5 points for comprehensive documentation

### Automated Validation
```bash
# 80% threshold = 4.8/6 exercises must pass
mise run test:all && echo "✅ Validation candidate"
```

**Total: 100 points**
- Exercise 1: 15 pts (Core - Security)
- Exercise 2: 15 pts (Core - Stability)  
- Exercise 3: 20 pts (Resilience)
- Exercise 4: 15 pts (Robustness)
- Exercise 5: 15 pts (Monitoring)
- Exercise 6: 20 pts (Core - Observability)

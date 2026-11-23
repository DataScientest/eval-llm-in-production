# LLMOps Production Readiness - Exam

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)

An **LLMOps exam** covering configuration management, graceful shutdown, fault tolerance, error handling, health checks, and structured logging.


### 6 Exercises

Instructions: [docs/EXAM.md](docs/EXAM.md) (English) or [docs/EXAM_fr.md](docs/EXAM_fr.md) (français).

| # | Topic | Status | Points |
|---|-------|--------|--------|
| 1 | Secure configuration | required | 30 |
| 2 | Error handling and retry | required | 35 |
| 3 | Structured logging | required | 35 |
| 4 | Graceful shutdown | bonus | +10 |
| 5 | Timeouts and request limits | bonus | +10 |
| 6 | Health checks | bonus | +10 |

Check an exercise on the running stack: `bash scripts/check_exercise.sh <1-6>`.


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

Each exercise has a check that runs against the stack started with `docker compose up -d`:

```bash
bash scripts/check_exercise.sh 1   # required: 1, 2, 3   bonus: 4, 5, 6
```

With [mise](https://mise.jdx.dev/) (optional):

```bash
mise run test:all    # required exercises 1 to 3
mise run test:ex4    # one exercise (ex1 to ex6)
mise run status      # check all services
mise run logs        # view API logs
mise run token       # get a JWT token
```

Get a token for manual calls:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret123"}' \
  | jq -r '.access_token')
```

The scenario and the expected behaviour of each exercise are described in [docs/EXAM.md](docs/EXAM.md).


## Project Structure

```sh
├── docs/EXAM.md, docs/EXAM_fr.md  # Student instructions (EN, FR)
├── docs/CORRECTION.md              # Grading guide (solution repo only)
├── .env.example                    # Environment template
├── docker-compose.yml              # Service orchestration
├── Makefile.curl                   # Test automation
│
├── src/api/
│   ├── main.py                     # API entry point
│   ├── config/
│   │   ├── settings.py             # Ex1: Pydantic BaseSettings
│   │   ├── env_validator.py        # Ex1: Startup validation
│   │   ├── lifespan.py             # Ex4: Graceful shutdown
│   │   ├── logging_config.py       # Ex3: JSON logging
│   │   └── app.py                  # Health endpoints
│   ├── middleware/
│   │   ├── shutdown.py             # Ex4: In-flight tracking
│   │   ├── request_limits.py       # Ex5: Body size limits
│   │   └── request_id.py           # Ex3: Request ID generation
│   ├── routers/
│   │   ├── llm.py                  # Ex5/Ex2: Timeouts, retry, errors
│   │   └── system.py               # Ex6: Health endpoints
│   ├── services/
│   │   ├── circuit_breaker.py      # Ex5: Circuit breaker pattern
│   │   └── health_checker.py       # Ex6: Dependency verification
│   └── utils/
│       └── retry.py                # Ex2: Exponential backoff
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
│  │ (Ex3)         │  │ Check (Ex4)   │  │ (Ex5: 1MB max)    │   │
│  └───────────────┘  └───────────────┘  └───────────────────┘   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Application                                            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Settings (Ex1)     │ Health Checks (Ex6)                  │  │
│  │ - Pydantic config  │ - /health (liveness)                 │  │
│  │ - JWT validation   │ - /health/detailed (readiness)       │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ LLM Router (Ex5, Ex2)                                     │  │
│  │ - Timeouts (30s request, 5s connect)                      │  │
│  │ - Circuit Breaker (5 failures → open)                     │  │
│  │ - Retry with exponential backoff                          │  │
│  │ - Granular error handling                                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Structured Logging (Ex3)                                  │  │
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

See the grading section of [docs/EXAM.md](docs/EXAM.md): exercises 1 to 3 are required (100 points, validation at 60/100), exercises 4 to 6 are bonus (+10 each).

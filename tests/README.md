# 🧪 Tests Suite

This directory contains comprehensive tests for the LLMOps security stack.

## 📂 Directory Structure

```
tests/
├── conftest.py                     # Shared pytest fixtures
├── unit/                           # Fast, isolated unit tests (22 tests)
│   └── services/
│       ├── test_auth_service.py    # Auth/JWT/password hashing tests
│       └── test_llm_service.py     # LLM service/retry/DI tests
├── integration/                    # Tests requiring running services
│   ├── test_auth_endpoints.py      # JWT auth flow
│   ├── test_cache_endpoints.py     # Cache behavior
│   └── test_api_endpoints.py       # API endpoints
├── test-cache-with-logs.sh         # Cache demo with log verification
├── test-cache-performance.sh       # Performance benchmarks
├── test-comprehensive.sh           # Full system test
└── test-semantic-cache.sh          # Semantic cache analysis
```

## 🚀 Running Tests

### Unit Tests (runs inside Docker)
```bash
mise run test:unit
```

### Integration Tests (requires running services)
```bash
mise run test:integration
```

### Exercise Tests (lifecycle testing)
```bash
mise run test:all    # All 6 exercises
mise run test:ex1    # Secure Configuration
mise run test:ex2    # Graceful Shutdown
mise run test:ex3    # Circuit Breaker
mise run test:ex4    # Error Handling
mise run test:ex5    # Health Checks
mise run test:ex6    # Structured Logging
```

### Shell Scripts
```bash
./tests/test-cache-with-logs.sh
./tests/test-cache-performance.sh
```

## 📋 Prerequisites

- Docker stack running: `docker compose up -d`
- All services healthy: `mise run status`

## 🔗 Related Files

- `src/api/services/llm_service.py` - LLM service with retry/cache logic
- `src/api/services/auth_service.py` - Authentication with bcrypt
- `src/api/cache/exact_cache.py` - Exact cache implementation
- `mise.toml` - Test task definitions

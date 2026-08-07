# 🧪 Tests Suite

This directory contains tests for verifying your exam solutions.

## 📂 Directory Structure

```
tests/
├── integration/                    # Integration tests
│   ├── test_auth_endpoints.py      # JWT auth flow
│   ├── test_cache_endpoints.py     # Cache behavior
│   └── test_api_endpoints.py       # API endpoints
├── test-cache-with-logs.sh         # Cache demo with log verification
├── test-cache-performance.sh       # Performance benchmarks
├── test-comprehensive.sh           # Full system test
└── test-semantic-cache.sh          # Semantic cache analysis
```

## 🚀 Running Tests

### Exercise Verification
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
- All services healthy

## 📝 Adding Your Own Tests

As you implement each exercise, consider adding tests to verify your solutions:

```
tests/
├── unit/                           # Create this for your unit tests
│   └── services/
│       ├── test_auth_service.py    # Test your auth improvements
│       └── test_retry.py           # Test your retry logic
└── conftest.py                     # Shared fixtures
```

# LLMOps Exam: Production Readiness

> Version française : [EXAM_fr.md](EXAM_fr.md)

## Overview

This repository contains a complete LLMOps stack (FastAPI, LiteLLM, Qdrant cache, MLflow, Prometheus, Grafana). It works, but six bad practices make it unsafe for production. Your job is to fix them.

- **Exercises 1 to 3 are required.** They build on notions seen in the courses *Integrating LLM in production* and *ML System Design*.
- **Exercises 4 to 6 are bonus.** They go beyond the courses. Each one comes with hints.

Each exercise has a check you can run yourself on the running stack:

```bash
docker compose up -d --build
bash scripts/check_exercise.sh 1    # 1 to 6
```

`[OK]` lines show what already works, `[FAIL]` lines show what is missing. On the starting code, every check fails.

### Setup

```bash
cp .env.example .env
# Set JWT_SECRET_KEY (openssl rand -hex 32) and GROQ_API_KEY (free key: https://console.groq.com/keys)
docker compose up -d --build
```

### Recommended workflow

```bash
git checkout -b fix/secure-config     # one branch per exercise
# implement, then check
bash scripts/check_exercise.sh 1
git commit -am "fix: secure configuration"
git checkout main && git merge fix/secure-config
```

---

## Required exercises

### Exercise 1: Secure configuration (30 pts)

**Problem.** `src/api/config/settings.py` ships a default `JWT_SECRET_KEY` (`"your-secret-key-change-in-production"`) and `CORS_ORIGINS = ["*"]`. If someone deploys without changing the secret, anyone can forge an admin token with the value read from the code.

**To do**
- [ ] Move the settings to `pydantic-settings` (`BaseSettings`), read from the environment.
- [ ] Refuse to start (fail fast) if `JWT_SECRET_KEY` is missing, equal to the default value, or shorter than 32 characters.
- [ ] Replace `CORS_ORIGINS = ["*"]` with an explicit list of origins.
- [ ] Complete `src/api/config/env_validator.py` (starting point provided) and call it at startup.
- [ ] Keep `.env.example` up to date with every required variable.

**Hints**
- Course reminders: secrets in environment variables (*ML System Design*, chapter 7); JWT authentication (*Integrating LLM in production*, chapter 3).
- `pydantic-settings`: a field without default value is required; a `@field_validator` can reject a weak value. Doc: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- The check imports `config.settings` with the default secret and expects the import to fail.

**Check:** `bash scripts/check_exercise.sh 1`

### Exercise 2: Error handling and retry (35 pts)

**Problem.** In `src/api/routers/llm.py`, every error ends in `except Exception` with a generic `{"detail": "Failed to generate response"}`. A transient network error is returned at once instead of being retried, and nothing allows support to find the incident in the logs.

**To do**
- [ ] Handle errors by type: rate limit (429), bad request or unknown model (400/404), connection or timeout (502/504).
- [ ] Return structured errors: error type, message, `incident_id`, `timestamp`.
- [ ] Retry transient errors (connection, timeout, rate limit) with exponential backoff: 1 s, 2 s, 4 s, 3 retries max. Complete `src/api/utils/retry.py` (starting point provided).
- [ ] Log each attempt, for example `Attempt 1/4 failed: APIConnectionError. Retrying in 1.1s`.
- [ ] If MLflow tracing fails, log the failure instead of silently ignoring it.

**Hints**
- Course reminders: retry with exponential backoff and circuit breaker (*ML System Design*, chapter 5); fallback between models with LiteLLM (*Integrating LLM in production*, chapter 1).
- Do not retry a client error (400, 404): it will fail again.
- Add some random jitter to the delay so that clients do not retry all at once.
- Library option: `tenacity` (https://tenacity.readthedocs.io). A small hand-written loop is accepted too.
- Set `max_retries=0` on the OpenAI client so that only your retry logic runs.

**Check:** `bash scripts/check_exercise.sh 2` (the check stops LiteLLM for a few seconds and expects retry attempts in the logs).

### Exercise 3: Structured logging (35 pts)

**Problem.** The code uses `print()` everywhere. When a request fails, nothing tells you which user or which request it was, and the logs cannot be parsed (`docker compose logs api | jq` fails).

**To do**
- [ ] Configure JSON logging in `src/api/config/logging_config.py` (starting point provided): one JSON object per line with at least `timestamp`, `level`, `message`, `request_id`.
- [ ] Complete the middleware `src/api/middleware/request_id.py` (starting point provided): generate a request ID, keep it for the whole request, return it in the `X-Request-ID` header.
- [ ] Replace every `print()` with `logger.debug/info/warning/error()` at the right level.
- [ ] Add the `request_id` to every log line written during a request.

**Hints**
- Course reminder: prediction log pattern, one unique ID per request (*ML System Design*, chapter 8).
- A `logging.Formatter` subclass that returns `json.dumps({...})` is enough. Doc: https://docs.python.org/3/library/logging.html
- `contextvars.ContextVar` keeps the request ID available in any function called during the request.
- Uvicorn access logs can stay as they are; your application logs must be JSON.

**Check:** `bash scripts/check_exercise.sh 3`

---

## Bonus exercises

These topics are not covered by the courses. Each one is worth extra points but cannot make you fail the exam.

### Exercise 4 (bonus): Graceful shutdown (+10 pts)

**Problem.** In `src/api/config/lifespan.py`, nothing happens after `yield`: on `docker compose stop api`, in-flight requests are cut, Qdrant connections are not closed and MLflow traces stay incomplete.

**To do**
- [ ] Track in-flight requests with a middleware (for example `src/api/middleware/shutdown.py`).
- [ ] On shutdown, wait for them to finish (30 s max), then close Qdrant and HTTP clients and end active MLflow runs.
- [ ] Log each step: `Waiting for 1 active request(s)...`, `Closing Qdrant connections...`, `Graceful shutdown completed in 2.3s`.

**Hints**
- FastAPI runs the code after `yield` in the lifespan function when the server stops. Doc: https://fastapi.tiangolo.com/advanced/events/
- A counter incremented and decremented by a middleware is enough to know how many requests are running.

**Check:** `bash scripts/check_exercise.sh 4`

### Exercise 5 (bonus): Timeouts and request limits (+10 pts)

**Problem.** The OpenAI client in `src/api/routers/llm.py` has no timeout: if LiteLLM hangs, every worker waits forever. The API also accepts request bodies of any size.

**To do**
- [ ] Set a timeout on the OpenAI client: 30 s for the request, 5 s to connect. Return 504 on timeout.
- [ ] Reject bodies larger than 1 MB with 413 (middleware `src/api/middleware/request_limits.py`).
- [ ] Optional: a circuit breaker that stops calling LiteLLM after 5 consecutive failures and returns 503 for a while.

**Hints**
- `openai.OpenAI(..., timeout=httpx.Timeout(30.0, connect=5.0))`. Doc: https://www.python-httpx.org/advanced/timeouts/
- A middleware can read the `Content-Length` header and answer 413 before reading the body.
- Circuit breaker: *ML System Design*, chapter 5.

**Check:** `bash scripts/check_exercise.sh 5`

### Exercise 6 (bonus): Health checks (+10 pts)

**Problem.** `/system/health` always answers `"healthy"`, even when Qdrant or LiteLLM is down. A load balancer would keep sending traffic to a broken instance.

**To do**
- [ ] `/health` (liveness): answers 200 as long as the application runs.
- [ ] `/health/detailed` (readiness): checks Qdrant, LiteLLM and MLflow; answers 200 if all are up, 503 with `"status": "degraded"` and the detail per dependency otherwise.
- [ ] Cache the results for 30 s (for example in `src/api/services/health_checker.py`).
- [ ] Use `/health` in the `api` healthcheck of `docker-compose.yml`.

**Hints**
- Liveness answers "is the process alive?", readiness answers "can it serve traffic?". Doc: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- Health checks are introduced in *Integrating LLM in production*, chapter 6.
- Check the dependencies in parallel with short timeouts so that `/health/detailed` stays fast.

**Check:** `bash scripts/check_exercise.sh 6` (the check stops Qdrant for about 35 s).

---

## Grading

| Exercise | Points |
|----------|--------|
| 1. Secure configuration | 30 |
| 2. Error handling and retry | 35 |
| 3. Structured logging | 35 |
| **Required total** | **100** |
| 4. Graceful shutdown (bonus) | +10 |
| 5. Timeouts and limits (bonus) | +10 |
| 6. Health checks (bonus) | +10 |

- **Validation:** at least 60/100 on exercises 1 to 3.
- A working but incomplete exercise gets half of its points.
- Bonus points are added to the final grade (capped at 100). They do not replace the required exercises.

## Deliverables

- Your repository with the fixed code (archive or link, as asked on the platform).
- An `IMPLEMENTATION.md` file at the root, with for each exercise: the problem, your solution, the command that shows it works.

## Final checklist

- [ ] `bash scripts/check_exercise.sh 1`, `2` and `3` print `PASSED`.
- [ ] Bonus exercises attempted: their check prints `PASSED`.
- [ ] `IMPLEMENTATION.md` is written.
- [ ] `.env` is not committed (it contains your API keys).

"""Retry with exponential backoff - Exercise 2 (starting point).

TODO Exercise 2: implement a retry helper for transient LLM errors.
- Retry only transient errors (connection, timeout, rate limit), never 400/404.
- Wait 1 s, 2 s, 4 s between attempts (3 retries max), with a little random jitter.
- Log every attempt, e.g. "Attempt 1/4 failed: APIConnectionError. Retrying in 1.1s".
See docs/EXAM.md, Exercise 2.
"""

import logging

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY_SECONDS = 1.0


def calculate_backoff_delay(attempt: int) -> float:
    """Return the delay before the next attempt (attempt starts at 0)."""
    # TODO Exercise 2: exponential backoff with jitter
    raise NotImplementedError


async def call_with_retry(func, *args, **kwargs):
    """Call func, retrying transient errors with exponential backoff."""
    # TODO Exercise 2: loop over the attempts, catch transient errors, log, sleep, retry
    raise NotImplementedError

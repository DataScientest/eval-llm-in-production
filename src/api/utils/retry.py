"""Retry utilities with exponential backoff."""

import asyncio
import logging
import random
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 16.0  # seconds
DEFAULT_EXPONENTIAL_BASE = 2
DEFAULT_JITTER = 0.1  # 10% jitter


def calculate_backoff_delay(
    attempt: int,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    exponential_base: int = DEFAULT_EXPONENTIAL_BASE,
    jitter: float = DEFAULT_JITTER,
) -> float:
    """
    Calculate delay with exponential backoff and jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap
        exponential_base: Base for exponential calculation
        jitter: Jitter factor (0.0 to 1.0)

    Returns:
        Delay in seconds
    """
    # Calculate exponential delay: base_delay * (exponential_base ^ attempt)
    delay = base_delay * (exponential_base**attempt)

    # Cap at max_delay
    delay = min(delay, max_delay)

    # Add jitter to prevent thundering herd
    jitter_amount = delay * jitter * random.random()
    delay = delay + jitter_amount

    return delay


def is_retryable_error(
    error: Exception,
    retryable_exceptions: Tuple[Type[Exception], ...],
) -> bool:
    """Check if an error is retryable."""
    return isinstance(error, retryable_exceptions)


async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    **kwargs,
) -> Any:
    """
    Execute a function with retry and exponential backoff.

    Args:
        func: Function to execute (can be sync or async)
        *args: Positional arguments for the function
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries
        max_delay: Maximum delay cap
        retryable_exceptions: Tuple of exceptions that should trigger retry
        on_retry: Optional callback called on each retry (attempt, error, delay)
        **kwargs: Keyword arguments for the function

    Returns:
        Result of the function

    Raises:
        The last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            # Check if function is async
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        except retryable_exceptions as e:
            last_exception = e

            # Don't retry on the last attempt
            if attempt >= max_retries:
                logger.error(
                    f"All {max_retries + 1} attempts failed for {func.__name__}: {e}"
                )
                raise

            # Calculate delay
            delay = calculate_backoff_delay(
                attempt=attempt,
                base_delay=base_delay,
                max_delay=max_delay,
            )

            logger.warning(
                f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                f"Retrying in {delay:.2f}s..."
            )

            # Call retry callback if provided
            if on_retry:
                on_retry(attempt, e, delay)

            # Wait before retry
            await asyncio.sleep(delay)

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception


def with_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator for adding retry logic with exponential backoff.

    Usage:
        @with_retry(max_retries=3, retryable_exceptions=(ConnectionError,))
        async def my_function():
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await retry_with_backoff(
                func,
                *args,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                retryable_exceptions=retryable_exceptions,
                **kwargs,
            )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to run in event loop
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(
                retry_with_backoff(
                    func,
                    *args,
                    max_retries=max_retries,
                    base_delay=base_delay,
                    max_delay=max_delay,
                    retryable_exceptions=retryable_exceptions,
                    **kwargs,
                )
            )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Pre-configured retry settings for common use cases
RETRYABLE_NETWORK_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,
)

RETRYABLE_HTTP_ERRORS = (
    ConnectionError,
    TimeoutError,
)

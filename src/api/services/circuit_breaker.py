"""Circuit breaker implementation for external service calls."""

import asyncio
import logging
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Failing, requests are rejected immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Protects against cascading failures by failing fast when a service
    is experiencing problems.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Name of the circuit (for logging)
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying again
            half_open_max_calls: Max calls allowed in half-open state
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self._state == CircuitState.OPEN

    async def _check_state_transition(self):
        """Check if state should transition based on timeout."""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    logger.info(
                        f"Circuit '{self.name}' transitioning from OPEN to HALF_OPEN "
                        f"after {elapsed:.1f}s"
                    )
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0

    async def record_success(self):
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info(f"Circuit '{self.name}' closing after successful call")
                self._state = CircuitState.CLOSED
                self._failure_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    async def record_failure(self, error: Exception = None):
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    f"Circuit '{self.name}' re-opening after failure in half-open state"
                )
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit '{self.name}' opening after {self._failure_count} failures"
                )
                self._state = CircuitState.OPEN

    async def can_execute(self) -> bool:
        """Check if a call can be executed."""
        async with self._lock:
            await self._check_state_transition()

            if self._state == CircuitState.CLOSED:
                return True
            elif self._state == CircuitState.OPEN:
                return False
            elif self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

        return False

    def get_status(self) -> dict:
        """Get circuit breaker status."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self._last_failure_time,
        }


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    def __init__(self, circuit_name: str, message: str = None):
        self.circuit_name = circuit_name
        self.message = message or f"Circuit '{circuit_name}' is open"
        super().__init__(self.message)


# Global circuit breakers for different services
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, **kwargs)
    return _circuit_breakers[name]


def get_all_circuit_breakers() -> dict[str, dict]:
    """Get status of all circuit breakers."""
    return {name: cb.get_status() for name, cb in _circuit_breakers.items()}


# Pre-configured circuit breakers for known services
litellm_circuit = get_circuit_breaker(
    "litellm",
    failure_threshold=5,
    recovery_timeout=30.0,
)

qdrant_circuit = get_circuit_breaker(
    "qdrant",
    failure_threshold=3,
    recovery_timeout=15.0,
)

mlflow_circuit = get_circuit_breaker(
    "mlflow",
    failure_threshold=5,
    recovery_timeout=60.0,
)

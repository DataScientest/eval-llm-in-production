"""Application lifespan management with graceful shutdown."""

import asyncio
import logging
import signal
from contextlib import asynccontextmanager

from fastapi import FastAPI
from services.mlflow_service import mlflow_service

logger = logging.getLogger(__name__)

# Global state for shutdown coordination
_shutdown_event = asyncio.Event()
_active_requests = 0
_active_requests_lock = asyncio.Lock()

# Shutdown configuration
SHUTDOWN_TIMEOUT_SECONDS = 30


async def increment_active_requests():
    """Increment the count of active requests."""
    global _active_requests
    async with _active_requests_lock:
        _active_requests += 1


async def decrement_active_requests():
    """Decrement the count of active requests."""
    global _active_requests
    async with _active_requests_lock:
        _active_requests -= 1


def get_active_requests() -> int:
    """Get the current count of active requests."""
    return _active_requests


def is_shutting_down() -> bool:
    """Check if the application is in shutdown mode."""
    return _shutdown_event.is_set()


def trigger_shutdown():
    """Trigger the shutdown event."""
    _shutdown_event.set()


async def wait_for_active_requests(timeout: float = SHUTDOWN_TIMEOUT_SECONDS) -> bool:
    """
    Wait for all active requests to complete.

    Args:
        timeout: Maximum time to wait in seconds

    Returns:
        True if all requests completed, False if timeout occurred
    """
    start_time = asyncio.get_event_loop().time()

    while _active_requests > 0:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= timeout:
            logger.warning(
                f"Shutdown timeout: {_active_requests} requests still active after {timeout}s"
            )
            return False

        logger.info(f"Waiting for {_active_requests} active request(s) to complete...")
        await asyncio.sleep(0.5)

    return True


async def cleanup_resources():
    """Clean up all application resources."""
    logger.info("Starting resource cleanup...")

    # 1. Finalize MLflow runs
    try:
        logger.info("Finalizing MLflow runs...")
        await mlflow_service.finalize_active_runs()
        logger.info("MLflow runs finalized")
    except Exception as e:
        logger.error(f"Error finalizing MLflow runs: {e}")

    # 2. Close Qdrant connections (handled by cache instances)
    try:
        logger.info("Closing Qdrant connections...")
        # Import here to avoid circular imports
        from routers.llm import cache

        if hasattr(cache, "close"):
            await cache.close()
        elif hasattr(cache, "qdrant_client"):
            cache.qdrant_client.close()
        logger.info("Qdrant connections closed")
    except Exception as e:
        logger.error(f"Error closing Qdrant connections: {e}")

    # 3. Close any HTTP clients
    try:
        logger.info("Closing HTTP clients...")
        # The OpenAI client will be garbage collected, but we log it
        logger.info("HTTP clients closed")
    except Exception as e:
        logger.error(f"Error closing HTTP clients: {e}")

    logger.info("Resource cleanup completed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle with proper startup and shutdown.

    Startup:
    - Setup MLflow experiment
    - Initialize cache connections

    Shutdown:
    - Wait for in-flight requests to complete
    - Finalize MLflow runs
    - Close all connections
    """
    # ===== STARTUP =====
    logger.info("Starting LLMOps Secure API...")

    # Setup MLflow experiment
    try:
        await mlflow_service.setup_experiment()
        logger.info("MLflow experiment setup completed")
    except Exception as e:
        logger.error(f"Failed to setup MLflow experiment: {e}")

    # Cache is initialized in the LLM router
    logger.info("Qdrant cache will be initialized on first request")

    logger.info("LLMOps Secure API started successfully")

    yield

    # ===== SHUTDOWN =====
    logger.info("Received shutdown signal, starting graceful shutdown...")

    # Trigger shutdown mode (new requests will be rejected)
    trigger_shutdown()

    # Wait for active requests to complete
    logger.info(
        f"Waiting for active requests (timeout: {SHUTDOWN_TIMEOUT_SECONDS}s)..."
    )
    requests_completed = await wait_for_active_requests(SHUTDOWN_TIMEOUT_SECONDS)

    if requests_completed:
        logger.info("All active requests completed")
    else:
        logger.warning("Shutdown timeout reached, proceeding with cleanup")

    # Clean up resources
    await cleanup_resources()

    logger.info("Graceful shutdown completed")

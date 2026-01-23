"""Health checker service for dependency monitoring."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
from config.settings import settings
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

logger = logging.getLogger(__name__)

# Health check configuration
HEALTH_CHECK_TIMEOUT = 5.0  # 5 seconds per check
CACHE_TTL_SECONDS = 30  # Cache health results for 30 seconds


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    healthy: bool

    healthy: bool
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CachedHealthResult:
    """Cached health check result with TTL."""

    cached_at: float = field(default_factory=time.time)

    def is_expired(self, ttl: float = CACHE_TTL_SECONDS) -> bool:
        """Check if the cached result has expired."""
        return time.time() - self.cached_at > ttl


class HealthChecker:
    """
    Health checker for external dependencies.

    Provides cached health checks for:
    - Qdrant (vector database)
    - LiteLLM (LLM proxy)
    - MLflow (tracking server)
    - TEI (embeddings service)
    """

    def __init__(self):
        self._cache: Dict[str, CachedHealthResult] = {}
        self._lock = asyncio.Lock()

    async def _get_cached_or_check(
        self,
        service_name: str,
        check_func,
    ) -> HealthCheckResult:
        """Get cached result or perform new health check."""
        async with self._lock:
            cached = self._cache.get(service_name)
            if cached and not cached.is_expired():
                logger.debug(f"Using cached health result for {service_name}")
                return cached.result

        # Perform new check
        result = await check_func()

        # Cache the result
        async with self._lock:
            self._cache[service_name] = CachedHealthResult(result=result)

        return result

    async def check_qdrant(self) -> HealthCheckResult:
        """Check Qdrant vector database health."""
        start_time = time.time()

        try:
            client = QdrantClient(url=settings.QDRANT_URL, timeout=HEALTH_CHECK_TIMEOUT)

            # Try to get collections as a health check
            collections = client.get_collections()

            latency_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                healthy=True,
                latency_ms=latency_ms,
                message="Qdrant is healthy",
                details={
                    "collections_count": len(collections.collections),
                    "url": settings.QDRANT_URL,
                },
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"Qdrant health check failed: {e}")
            return HealthCheckResult(
                healthy=False,
                latency_ms=latency_ms,
                message=f"Qdrant connection failed: {str(e)[:100]}",
                details={"url": settings.QDRANT_URL},
            )

    async def check_litellm(self) -> HealthCheckResult:
        """Check LiteLLM proxy health."""
        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
                # Try to get models endpoint
                response = await client.get(f"{settings.LITELLM_URL}/health")

                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    return HealthCheckResult(
                        healthy=True,
                        latency_ms=latency_ms,
                        message="LiteLLM is healthy",
                        details={
                            "url": settings.LITELLM_URL,
                            "status_code": response.status_code,
                        },
                    )
                else:
                    return HealthCheckResult(
                        healthy=False,
                        latency_ms=latency_ms,
                        message=f"LiteLLM returned status {response.status_code}",
                        details={
                            "url": settings.LITELLM_URL,
                            "status_code": response.status_code,
                        },
                    )
        except httpx.TimeoutException:
            latency_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                healthy=False,
                latency_ms=latency_ms,
                message="LiteLLM request timed out",
                details={"url": settings.LITELLM_URL, "timeout": HEALTH_CHECK_TIMEOUT},
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"LiteLLM health check failed: {e}")
            return HealthCheckResult(
                healthy=False,
                latency_ms=latency_ms,
                message=f"LiteLLM connection failed: {str(e)[:100]}",
                details={"url": settings.LITELLM_URL},
            )

    async def check_mlflow(self) -> HealthCheckResult:
        """Check MLflow tracking server health."""
        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
                # MLflow health endpoint
                response = await client.get(f"{settings.MLFLOW_TRACKING_URI}/health")

                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    return HealthCheckResult(
                        healthy=True,
                        latency_ms=latency_ms,
                        message="MLflow is healthy",
                        details={
                            "url": settings.MLFLOW_TRACKING_URI,
                            "status_code": response.status_code,
                        },
                    )
                else:
                    return HealthCheckResult(
                        healthy=False,
                        latency_ms=latency_ms,
                        message=f"MLflow returned status {response.status_code}",
                        details={
                            "url": settings.MLFLOW_TRACKING_URI,
                            "status_code": response.status_code,
                        },
                    )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"MLflow health check failed: {e}")
            return HealthCheckResult(
                healthy=False,
                latency_ms=latency_ms,
                message=f"MLflow connection failed: {str(e)[:100]}",
                details={"url": settings.MLFLOW_TRACKING_URI},
            )

    async def check_tei(self) -> HealthCheckResult:
        """Check TEI embeddings service health."""
        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
                response = await client.get(f"{settings.TEI_URL}/health")

                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    return HealthCheckResult(
                        healthy=True,
                        latency_ms=latency_ms,
                        message="TEI embeddings is healthy",
                        details={
                            "url": settings.TEI_URL,
                            "status_code": response.status_code,
                        },
                    )
                else:
                    return HealthCheckResult(
                        healthy=False,
                        latency_ms=latency_ms,
                        message=f"TEI returned status {response.status_code}",
                        details={
                            "url": settings.TEI_URL,
                            "status_code": response.status_code,
                        },
                    )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"TEI health check failed: {e}")
            return HealthCheckResult(
                healthy=False,
                latency_ms=latency_ms,
                message=f"TEI connection failed: {str(e)[:100]}",
                details={"url": settings.TEI_URL},
            )

    async def check_all(self, use_cache: bool = True) -> Dict[str, HealthCheckResult]:
        """
        Check all dependencies.

        Args:
            use_cache: Whether to use cached results (default: True)

        Returns:
            Dictionary of service names to health check results
        """
        if use_cache:
            # Use cached results where available
            results = await asyncio.gather(
                self._get_cached_or_check("qdrant", self.check_qdrant),
                self._get_cached_or_check("litellm", self.check_litellm),
                self._get_cached_or_check("mlflow", self.check_mlflow),
                self._get_cached_or_check("tei", self.check_tei),
            )
        else:
            # Force fresh checks
            results = await asyncio.gather(
                self.check_qdrant(),
                self.check_litellm(),
                self.check_mlflow(),
                self.check_tei(),
            )

        return {
            "qdrant": results[0],
            "litellm": results[1],
            "mlflow": results[2],
            "tei": results[3],
        }

    def clear_cache(self):
        """Clear the health check cache."""
        self._cache.clear()


# Global health checker instance
health_checker = HealthChecker()

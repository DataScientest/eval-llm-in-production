"""Metrics middleware for capturing request metrics."""

import time
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram
import logging
from typing import Union

logger = logging.getLogger(__name__)

# =============================================================================
# REQUEST METRICS (kept here - middleware-specific)
# =============================================================================

REQUEST_COUNT = Counter(
    'llmops_requests_total', 
    'Total requests', 
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'llmops_request_duration_seconds', 
    'Request duration in seconds',
    ['method', 'endpoint']
)

REQUEST_SIZE = Histogram(
    'llmops_request_size_bytes',
    'Request size in bytes',
    ['method', 'endpoint']
)

RESPONSE_SIZE = Histogram(
    'llmops_response_size_bytes',
    'Response size in bytes',
    ['method', 'endpoint']
)

# =============================================================================
# CACHE METRICS - imported from centralized module
# =============================================================================
from metrics.cache_metrics import (
    CACHE_HITS,
    CACHE_LATENCY,
    CACHE_SIMILARITY_SCORE,
    CACHE_SIMILARITY_QUALITY,
    CACHE_HIT_RATIO,
    CACHE_PERFORMANCE_SAVINGS,
    CACHE_AVG_SEMANTIC_SIMILARITY,
    record_cache_hit,
    record_cache_miss,
    update_cache_ratio,
    record_performance_savings,
    record_semantic_similarity,
)

def _get_endpoint_from_request(request: Request) -> str:
    """Extract and normalize endpoint path from request."""
    endpoint = str(request.url.path)
    if endpoint.startswith('/'):
        endpoint = endpoint[1:]
    if not endpoint:
        endpoint = "root"
    return endpoint

def _get_content_length(headers) -> int:
    """Safely extract content length from headers."""
    try:
        return int(headers.get("content-length", 0))
    except (ValueError, TypeError):
        return 0

def _get_response_size(response: Union[Response, JSONResponse]) -> int:
    """Safely extract response size."""
    try:
        if hasattr(response, 'body'):
            # For Response objects with body attribute
            body = response.body
            if isinstance(body, bytes):
                return len(body)
            elif isinstance(body, str):
                return len(body.encode('utf-8'))
        
        # Try to get from headers
        if hasattr(response, 'headers'):
            content_length = response.headers.get("content-length")
            if content_length:
                return int(content_length)
        
        return 0
    except (ValueError, TypeError, AttributeError):
        return 0

async def metrics_middleware(request: Request, call_next):
    """Enhanced metrics middleware with better error handling and performance optimization."""
    start_time = time.time()
    method = request.method
    endpoint = _get_endpoint_from_request(request)
    
    # Skip metrics collection for certain endpoints to reduce overhead
    if endpoint in ["health", "docs", "redoc", "openapi.json"]:
        return await call_next(request)
    
    # Capture request size without consuming body
    request_size = _get_content_length(request.headers)
    if request_size > 0:
        try:
            REQUEST_SIZE.labels(method=method, endpoint=endpoint).observe(request_size)
        except Exception as e:
            logger.warning(f"Failed to record request size metric: {e}")
    
    response = None
    status_code = "500"  # Default to 500 in case of unexpected errors
    
    try:
        # Call next middleware/handler
        response = await call_next(request)
        
        # Extract status code from response
        if hasattr(response, 'status_code'):
            status_code = str(response.status_code)
        else:
            # Fallback for responses without status_code attribute
            status_code = "200"
        
        # Capture response size
        response_size = _get_response_size(response)
        if response_size > 0:
            try:
                RESPONSE_SIZE.labels(method=method, endpoint=endpoint).observe(response_size)
            except Exception as e:
                logger.warning(f"Failed to record response size metric: {e}")
        
    except Exception as e:
        # Handle any exception that occurs during request processing
        status_code = "500"
        
        # Log the error with context
        duration = time.time() - start_time
        logger.error(
            f"Request {method} {endpoint} - EXCEPTION - {duration:.3f}s: {type(e).__name__}: {e}",
            exc_info=True
        )
        
        # Record error metrics with exception handling
        try:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status_code).inc()
            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
        except Exception as metric_error:
            logger.warning(f"Failed to record error metrics: {metric_error}")
        
        # Re-raise the exception to maintain the middleware chain
        raise
    
    finally:
        # Always record metrics, even if an exception occurred
        # This ensures we capture timing even for failed requests
        duration = time.time() - start_time
        
        # Record successful request metrics (only if no exception occurred)
        if response is not None:
            try:
                REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status_code).inc()
                REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
                
                # Log successful request (only for non-metrics endpoints to reduce noise)
                if not endpoint.startswith("monitoring"):
                    logger.debug(f"Request {method} {endpoint} - {status_code} - {duration:.3f}s")
            except Exception as e:
                logger.warning(f"Failed to record success metrics: {e}")
    
    return response

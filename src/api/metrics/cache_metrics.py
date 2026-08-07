"""
Centralized Cache Metrics Module

All cache-related Prometheus metrics are defined here to avoid duplication
and provide a single source of truth for cache instrumentation.
"""

from prometheus_client import Counter, Histogram, Gauge

# =============================================================================
# CACHE COUNTERS
# =============================================================================

CACHE_HITS = Counter(
    'llmops_cache_hits_total',
    'Total cache hits by type',
    ['cache_type']  # 'exact', 'semantic', 'miss'
)

CACHE_SIMILARITY_QUALITY = Counter(
    'llmops_cache_similarity_quality_total',
    'Count of semantic cache hits by similarity quality',
    ['quality']  # 'excellent', 'good', 'fair', 'poor'
)

# =============================================================================
# CACHE HISTOGRAMS
# =============================================================================

CACHE_LATENCY = Histogram(
    'llmops_cache_latency_seconds',
    'Cache lookup latency in seconds',
    ['cache_type']  # 'exact', 'semantic'
)

CACHE_SIMILARITY_SCORE = Histogram(
    'llmops_cache_similarity_score',
    'Semantic cache similarity scores',
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0)
)

# =============================================================================
# CACHE GAUGES
# =============================================================================

CACHE_HIT_RATIO = Gauge(
    'llmops_cache_hit_ratio',
    'Cache hit ratio by type',
    ['cache_type']  # 'exact', 'semantic'
)

CACHE_PERFORMANCE_SAVINGS = Gauge(
    'llmops_cache_performance_savings_ms',
    'Performance savings from cache hits in milliseconds',
    ['cache_type']  # 'exact', 'semantic'
)

CACHE_AVG_SEMANTIC_SIMILARITY = Gauge(
    'llmops_cache_avg_semantic_similarity',
    'Average semantic similarity score for cache hits'
)

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def record_cache_hit(cache_type: str, latency_seconds: float):
    """Record a cache hit with latency."""
    CACHE_HITS.labels(cache_type=cache_type).inc()
    CACHE_LATENCY.labels(cache_type=cache_type).observe(latency_seconds)


def record_cache_miss():
    """Record a cache miss."""
    CACHE_HITS.labels(cache_type="miss").inc()


def update_cache_ratio(exact_hits: float, misses: float):
    """Update the cache hit ratio gauge."""
    total = exact_hits + misses
    if total > 0:
        CACHE_HIT_RATIO.labels(cache_type="exact").set(exact_hits / total)


def record_performance_savings(cache_type: str, savings_ms: float):
    """Record estimated time saved by cache hit."""
    CACHE_PERFORMANCE_SAVINGS.labels(cache_type=cache_type).set(savings_ms)


def record_semantic_similarity(similarity_score: float):
    """Record semantic similarity score and update quality counters."""
    CACHE_SIMILARITY_SCORE.observe(similarity_score)
    CACHE_AVG_SEMANTIC_SIMILARITY.set(similarity_score)
    
    # Categorize quality
    if similarity_score >= 0.95:
        CACHE_SIMILARITY_QUALITY.labels(quality="excellent").inc()
    elif similarity_score >= 0.85:
        CACHE_SIMILARITY_QUALITY.labels(quality="good").inc()
    elif similarity_score >= 0.75:
        CACHE_SIMILARITY_QUALITY.labels(quality="fair").inc()
    else:
        CACHE_SIMILARITY_QUALITY.labels(quality="poor").inc()

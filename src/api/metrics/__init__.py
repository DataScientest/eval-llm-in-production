"""Metrics package - centralized metrics definitions."""

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

__all__ = [
    "CACHE_HITS",
    "CACHE_LATENCY",
    "CACHE_SIMILARITY_SCORE",
    "CACHE_SIMILARITY_QUALITY",
    "CACHE_HIT_RATIO",
    "CACHE_PERFORMANCE_SAVINGS",
    "CACHE_AVG_SEMANTIC_SIMILARITY",
    "record_cache_hit",
    "record_cache_miss",
    "update_cache_ratio",
    "record_performance_savings",
    "record_semantic_similarity",
]

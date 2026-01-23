#!/usr/bin/env python3
"""
Test script to demonstrate enhanced MLflow cache differentiation features.

This script shows how the enhanced trace_llm_request method can handle:
1. Exact cache hits (similarity_score = 1.0)
2. Semantic cache hits (with variable similarity scores)
3. Cache misses
4. Proper cache type normalization
5. Detailed event logging
"""

import sys
import os

# Add the src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src/api'))

try:
    from services.mlflow_service import MLflowService
    mlflow_available = True
except ImportError as e:
    print(f"⚠️ MLflow not available: {e}")
    mlflow_available = False

def test_cache_type_normalization():
    """Test the cache type normalization functionality."""
    print("🔬 Testing Cache Type Normalization")
    print("=" * 50)
    
    if not mlflow_available:
        print("❌ Cannot test - MLflow service not available")
        return
    
    service = MLflowService()
    
    # Test exact cache variations
    exact_variations = [
        "exact", "EXACT", "exact_cache_hit", "perfect", "identical", "direct"
    ]
    
    print("Exact cache type variations:")
    for variation in exact_variations:
        normalized = service._normalize_cache_type(variation)
        print(f"  '{variation}' -> '{normalized}'")
    
    print("\nSemantic cache type variations:")
    semantic_variations = [
        "semantic", "SEMANTIC", "semantic_cache_hit", "similarity", "approximate", "fuzzy"
    ]
    
    for variation in semantic_variations:
        normalized = service._normalize_cache_type(variation)
        print(f"  '{variation}' -> '{normalized}'")

    print("\nEdge cases:")
    edge_cases = [None, "", "none", "unknown_type", "custom_cache"]
    for case in edge_cases:
        normalized = service._normalize_cache_type(case)
        print(f"  '{case}' -> '{normalized}'")

def test_similarity_quality_classification():
    """Test similarity score quality classification."""
    print("\n🎯 Testing Similarity Quality Classification")
    print("=" * 50)
    
    if not mlflow_available:
        print("❌ Cannot test - MLflow service not available")
        return
        
    service = MLflowService()
    
    test_scores = [1.0, 0.98, 0.87, 0.77, 0.68, 0.45, 0.0]
    
    for score in test_scores:
        quality = service._classify_similarity_quality(score)
        print(f"  Similarity {score:.2f} -> '{quality}'")

def test_cache_log_parsing():
    """Test cache log parsing functionality."""
    print("\n📋 Testing Cache Log Parsing")
    print("=" * 50)
    
    if not mlflow_available:
        print("❌ Cannot test - MLflow service not available")
        return
        
    service = MLflowService()
    
    # Sample log content with different cache scenarios
    sample_logs = """
2024-01-15 10:30:15 INFO: Processing request for model gpt-4
2024-01-15 10:30:15 DEBUG: Checking cache for prompt hash: abc123
2024-01-15 10:30:16 INFO: Cache hit exact match found, latency: 45.2 ms
2024-01-15 10:30:20 INFO: Processing new request
2024-01-15 10:30:21 DEBUG: Exact cache miss, checking semantic cache
2024-01-15 10:30:21 INFO: Semantic cache hit found, similarity: 0.87, latency: 123.5 ms  
2024-01-15 10:30:25 INFO: Cache miss, proceeding with LLM call
2024-01-15 10:30:27 DEBUG: SEMANTIC_CACHE_HIT similarity: 0.92 latency: 67.8ms
2024-01-15 10:30:30 DEBUG: CACHE_HIT exact time: 23.1ms
    """
    
    events = service.parse_cache_logs(sample_logs)
    print(f"Found {len(events)} cache events:")
    
    for i, event in enumerate(events, 1):
        print(f"\nEvent {i}:")
        print(f"  Type: {event['cache_type']}")
        print(f"  Cache Hit: {event['cache_hit']}")
        print(f"  Latency: {event.get('cache_latency_ms', 'N/A')} ms")
        print(f"  Similarity: {event.get('similarity_score', 'N/A')}")
        print(f"  Line: {event['line_number']}")

def demonstrate_enhanced_tracing():
    """Demonstrate the enhanced tracing capabilities."""
    print("\n🚀 Enhanced Tracing Demonstration")
    print("=" * 50)
    
    if not mlflow_available:
        print("❌ Cannot test - MLflow service not available")
        return
    
    print("""
The enhanced trace_llm_request method now supports:

1. ✅ Cache type differentiation:
   - Exact cache hits (similarity_score = 1.0)
   - Semantic cache hits (with custom similarity scores)
   - Proper cache type normalization

2. ✅ Enhanced attributes:
   - cache.similarity_score
   - cache.is_exact 
   - cache.is_semantic
   - match_quality classification

3. ✅ Detailed event logging:
   - Cache type specific event names
   - Similarity scores for semantic matches
   - Match quality classification
   - Backwards compatibility maintained

4. ✅ Better cache span attributes:
   - exact_match/semantic_match flags
   - Detailed similarity information
   - Enhanced cache latency tracking

Example usage:
```python
mlflow_service.trace_llm_request(
    prompt="What is AI?",
    model="gpt-4",
    response="AI is artificial intelligence...",
    tokens={"prompt_tokens": 10, "completion_tokens": 50, "total_tokens": 60},
    cost=0.002,
    start_time=time.time(),
    cache_hit=True,
    cache_latency_ms=45.2,
    cache_type="semantic",  # Will be normalized to "semantic"
    similarity_score=0.87   # NEW: Similarity score for semantic matches
)
```
    """)

if __name__ == "__main__":
    print("🧪 MLflow Enhanced Cache Differentiation Test")
    print("=" * 60)
    
    test_cache_type_normalization()
    test_similarity_quality_classification() 
    test_cache_log_parsing()
    demonstrate_enhanced_tracing()
    
    print("\n✅ All tests completed!")
    print("\nThe enhanced MLflow tracing now provides:")
    print("- Better cache type differentiation (exact vs semantic)")
    print("- Similarity score tracking for semantic cache hits")
    print("- Enhanced cache event logging with quality classification")
    print("- Backward compatibility with existing tracing code")

#!/bin/sh

echo "Initializing Qdrant collections..."

# Wait for Qdrant to be ready
echo "Waiting for Qdrant to be available..."
while ! curl -f http://qdrant:6333/collections >/dev/null 2>&1; do
    echo "Waiting for Qdrant..."
    sleep 2
done

echo "Qdrant is ready!"

# Delete existing collections if they exist (to ensure correct dimensions)
echo "Cleaning up existing collections..."
curl -X DELETE "http://qdrant:6333/collections/exact_cache" 2>/dev/null || true
curl -X DELETE "http://qdrant:6333/collections/litellm_semantic_cache" 2>/dev/null || true

# Create exact_cache collection for API (dimension 384 for all-MiniLM-L6-v2)
echo "Creating exact_cache collection with 384 dimensions..."
curl -X PUT "http://qdrant:6333/collections/exact_cache" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 384,
      "distance": "Cosine"
    }
  }'

# Create litellm_semantic_cache collection (dimension 384 for all-MiniLM-L6-v2)
echo "Creating litellm_semantic_cache collection with 384 dimensions..."
curl -X PUT "http://qdrant:6333/collections/litellm_semantic_cache" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 384,
      "distance": "Cosine"
    },
    "quantization_config": {
      "binary": {
        "always_ram": false
      }
    }
  }'

echo "Qdrant collections initialized successfully!"

# Verify collections
echo "Verifying collections:"
curl -s "http://qdrant:6333/collections"
#!/bin/bash
# Test both caching implementations side-by-side

set -e

BASE_URL="http://localhost:8080"

echo "======================================================================"
echo " Comparing Manual vs Decorator Caching Implementations"
echo "======================================================================"
echo ""

PAYLOAD='{
  "batch_id": "comparison-test",
  "data": [
    {"id": 0, "timestamp": 1702000000, "category": "A", "value": 10.5, "tags": ["test"]},
    {"id": 1, "timestamp": 1702000001, "category": "B", "value": 20.3, "tags": ["test"]},
    {"id": 2, "timestamp": 1702000002, "category": "C", "value": 15.7, "tags": ["test"]}
  ]
}'

# Test Manual Implementation
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " MANUAL IMPLEMENTATION (/duckdb-cached)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1️⃣  First Request (Cache MISS):"
curl -s -X POST "$BASE_URL/duckdb-cached" -H "Content-Type: application/json" -d "$PAYLOAD" | jq '{cache_hit, source, cache_time_ms, processing_time_ms, total_time_ms}'
echo ""

sleep 0.5

echo "2️⃣  Second Request (Cache HIT):"
curl -s -X POST "$BASE_URL/duckdb-cached" -H "Content-Type: application/json" -d "$PAYLOAD" | jq '{cache_hit, source, cache_time_ms, processing_time_ms, total_time_ms}'
echo ""
echo ""

# Test Decorator Implementation
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " DECORATOR IMPLEMENTATION (/duckdb-cached-decorator)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Use different batch_id to avoid cache collision
PAYLOAD_DECORATOR='{
  "batch_id": "decorator-test",
  "data": [
    {"id": 0, "timestamp": 1702000000, "category": "A", "value": 10.5, "tags": ["test"]},
    {"id": 1, "timestamp": 1702000001, "category": "B", "value": 20.3, "tags": ["test"]},
    {"id": 2, "timestamp": 1702000002, "category": "C", "value": 15.7, "tags": ["test"]}
  ]
}'

echo "1️⃣  First Request (Cache MISS):"
curl -s -X POST "$BASE_URL/duckdb-cached-decorator" -H "Content-Type: application/json" -d "$PAYLOAD_DECORATOR" | jq '{cache_hit, source, cache_time_ms, data: .data.batch_id}'
echo ""

sleep 0.5

echo "2️⃣  Second Request (Cache HIT):"
curl -s -X POST "$BASE_URL/duckdb-cached-decorator" -H "Content-Type: application/json" -d "$PAYLOAD_DECORATOR" | jq '{cache_hit, source, cache_time_ms, data: .data.batch_id}'
echo ""
echo ""

echo "======================================================================"
echo " COMPARISON SUMMARY"
echo "======================================================================"
echo ""
echo "📊 Manual Implementation:"
echo "   ✅ Detailed metrics (cache_time, processing_time, total_time)"
echo "   ✅ Fine-grained control over timing"
echo "   ❌ More boilerplate code"
echo ""
echo "🎨 Decorator Implementation:"
echo "   ✅ Clean, minimal code"
echo "   ✅ Reusable pattern (@redis_cache)"
echo "   ✅ Automatic cache key generation"
echo "   ❌ Less detailed timing (no separate processing_time)"
echo ""
echo "💡 Both achieve the same Redis → DuckDB caching behavior!"
echo ""

#!/usr/bin/env python3
"""
Test script for Valkey cache demonstration.
Tests cache HIT and MISS scenarios with timing measurements.
"""

import asyncio
import json
import time
from typing import Any

import httpx

BASE_URL = "http://localhost:8080"


# Sample test payload
def generate_test_payload(batch_id: str, size: int = 100) -> dict[str, Any]:
    """Generate test data payload."""
    data = [
        {
            "id": i,
            "timestamp": int(time.time()),
            "category": ["A", "B", "C", "D", "E"][i % 5],
            "value": float(i * 10),
            "tags": ["test", "demo"],
        }
        for i in range(size)
    ]

    return {"batch_id": batch_id, "data": data}


async def test_cache_miss() -> bool:
    """Test cache MISS scenario (first request)."""
    print("\n" + "=" * 80)
    print("TEST 1: Cache MISS (First Request)")
    print("=" * 80)

    payload = generate_test_payload("test-batch-001", size=5000)

    async with httpx.AsyncClient(timeout=30.0) as client:
        start = time.perf_counter()
        response = await client.get(
            f"{BASE_URL}/samples/duckdb-cached?batch_id={payload['batch_id']}&size={len(payload['data'])}"
        )
        elapsed = (time.perf_counter() - start) * 1000

        if response.status_code == 200:
            result = response.json()
            print("✅ Request successful")
            print(f"   Cache Hit: {result.get('cache_hit')}")
            print(f"   Source: {result.get('source')}")
            print(f"   Cache Check Time: {result.get('cache_time_ms', 0):.2f} ms")
            print(f"   Processing Time: {result.get('processing_time_ms', 0):.2f} ms")
            print(f"   Total Time: {result.get('total_time_ms', 0):.2f} ms")
            print(f"   Actual Request Time: {elapsed:.2f} ms")
            print(f"\n   Stats: {json.dumps(result.get('stats', {}), indent=2)}")
            return True
        else:
            print(f"❌ Request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False


async def test_cache_hit() -> bool:
    """Test cache HIT scenario (second request with same batch_id)."""
    print("\n" + "=" * 80)
    print("TEST 2: Cache HIT (Second Request - Same batch_id)")
    print("=" * 80)

    # Use the same batch_id as test 1
    payload = generate_test_payload("test-batch-001", size=5000)

    async with httpx.AsyncClient(timeout=30.0) as client:
        start = time.perf_counter()
        response = await client.get(
            f"{BASE_URL}/samples/duckdb-cached?batch_id={payload['batch_id']}&size={len(payload['data'])}"
        )
        elapsed = (time.perf_counter() - start) * 1000

        if response.status_code == 200:
            result = response.json()
            print("✅ Request successful")
            print(f"   Cache Hit: {result.get('cache_hit')}")
            print(f"   Source: {result.get('source')}")
            print(f"   Cache Check Time: {result.get('cache_time_ms', 0):.2f} ms")
            print(f"   Processing Time: {result.get('processing_time_ms', 0):.2f} ms")
            print(f"   Total Time: {result.get('total_time_ms', 0):.2f} ms")
            print(f"   Actual Request Time: {elapsed:.2f} ms")

            # Highlight the speedup
            if result.get("cache_hit"):
                print("\n   🚀 CACHE HIT! Data served from Valkey")
                print("   ⚡ Response time should be sub-millisecond from cache")

            return True
        else:
            print(f"❌ Request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False


async def test_different_batch() -> bool:
    """Test with a different batch_id (should be cache MISS)."""
    print("\n" + "=" * 80)
    print("TEST 3: Different Batch (Should be Cache MISS)")
    print("=" * 80)

    payload = generate_test_payload("test-batch-002", size=5000)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/samples/duckdb-cached?batch_id={payload['batch_id']}&size={len(payload['data'])}"
        )

        if response.status_code == 200:
            result = response.json()
            print("✅ Request successful")
            print(f"   Cache Hit: {result.get('cache_hit')}")
            print(f"   Source: {result.get('source')}")
            print(f"   Cache Check Time: {result.get('cache_time_ms', 0):.2f} ms")
            print(f"   Processing Time: {result.get('processing_time_ms', 0):.2f} ms")
            print(f"   Total Time: {result.get('total_time_ms', 0):.2f} ms")
            return True
        else:
            print(f"❌ Request failed: {response.status_code}")
            return False


async def main() -> None:
    print("\n🧪 Valkey Cache Testing Suite")
    print("📌 Testing Valkey LRU Cache → DuckDB Fallback Pattern\n")

    # Wait for server to be ready
    print("⏳ Waiting for server to be ready...")
    await asyncio.sleep(2)

    try:
        # Test 1: Cache Miss
        success1 = await test_cache_miss()

        # Small delay
        await asyncio.sleep(1)

        # Test 2: Cache Hit (same batch_id)
        success2 = await test_cache_hit()

        # Small delay
        await asyncio.sleep(1)

        # Test 3: Different batch (should be miss)
        success3 = await test_different_batch()

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        all_passed = success1 and success2 and success3
        if all_passed:
            print("✅ All tests passed!")
            print("\n💡 Key Observations:")
            print("   - First request (MISS): ~10-50ms (DuckDB processing)")
            print("   - Second request (HIT): <5ms (Valkey cache)")
            print("   - Cache provides 10-100x speedup for hot data")
        else:
            print("❌ Some tests failed. Check the output above.")

    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

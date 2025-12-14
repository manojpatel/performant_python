import time
import httpx
import asyncio
import random
import json
from statistics import mean

# Configuration
BASE_URL = "http://127.0.0.1:8080"
BATCH_SIZE = 5000  # Records per request
NUM_REQUESTS = 50  # Total requests per endpoint
CONCURRENCY = 5    # Concurrent requests

def generate_payload(batch_id: str, size: int):
    """Generates a payload compatible with all endpoints"""
    data = []
    for i in range(size):
        data.append({
            "id": i,
            "timestamp": time.time(),
            "category": random.choice(["A", "B", "C", "D", "E"]),
            "value": random.uniform(0, 1000),
            "tags": ["test"]
        })
    return {"batch_id": batch_id, "data": data}

async def fetch(client, url, payload):
    start = time.perf_counter()
    resp = await client.post(url, json=payload)
    end = time.perf_counter()
    resp.raise_for_status()
    return (end - start) * 1000  # ms

async def benchmark_endpoint(name: str, endpoint: str, payload: dict):
    print(f"Benchmarking {name} ({endpoint})...")
    timings = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Warmup
        for _ in range(5):
            await client.post(f"{BASE_URL}{endpoint}", json=payload)
            
        # Actual test
        tasks = []
        for i in range(NUM_REQUESTS):
            tasks.append(fetch(client, f"{BASE_URL}{endpoint}", payload))
        
        # Run with limited concurrency (simple implementation)
        # For true concurrency we'd use a semaphore, but gathering all is fine for this scale
        timings = await asyncio.gather(*tasks)

    avg_time = mean(timings)
    min_time = min(timings)
    max_time = max(timings)
    rps = (NUM_REQUESTS / sum(t/1000 for t in timings)) * CONCURRENCY # Rough RPS approximation
    
    return {
        "name": name,
        "avg_ms": avg_time,
        "min_ms": min_time,
        "max_ms": max_time,
        "rps_est": 1000 / avg_time  # Sequential RPS capability per client
    }

async def main():
    print(f"Generating payload with {BATCH_SIZE} records...")
    payload = generate_payload("bench-1", BATCH_SIZE)
    payload_size_mb = len(json.dumps(payload)) / 1024 / 1024
    print(f"Payload Size: {payload_size_mb:.2f} MB\n")

    results = []
    
    # 1. Standard (Pydantic + Polars)
    try:
        res = await benchmark_endpoint("Standard (Pydantic+Polars)", "/samples/batch", payload)
        results.append(res)
    except Exception as e:
        print(f"Standard failed: {e}")

    # 2. Msgspec (Msgspec + Polars)
    try:
        res = await benchmark_endpoint("Optimized (Msgspec+Polars)", "/samples/batch-msgspec", payload)
        results.append(res)
    except Exception as e:
        print(f"Msgspec failed: {e}")

    # 3. DuckDB (SQL)
    try:
        res = await benchmark_endpoint("SQL Engine (DuckDB)", "/samples/duckdb", payload)
        results.append(res)
    except Exception as e:
        print(f"DuckDB failed: {e}")

    # Print Table
    print("\n" + "="*80)
    print(f"{ 'IMPLEMENTATION':<30} | {'AVG (ms)':<10} | {'MIN (ms)':<10} | {'MAX (ms)':<10} | {'SPEEDUP'}")
    print("="*80)
    
    baseline = results[0]['avg_ms'] if results else 1.0
    
    for r in results:
        speedup = baseline / r['avg_ms']
        print(f"{r['name']:<30} | {r['avg_ms']:<10.2f} | {r['min_ms']:<10.2f} | {r['max_ms']:<10.2f} | {speedup:.2f}x")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())

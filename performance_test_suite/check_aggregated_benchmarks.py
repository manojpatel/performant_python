import asyncio
import sys
import os
import time
import statistics
from collections import defaultdict

# Add src to path
sys.path.append(os.getcwd())

from src.lib.duckdb_client import init_pool
from src.lib.valkey_cache import init_valkey_cache
from performance_test_suite.iceberg_runner import run_iceberg_benchmarks

ITERATIONS = 5

async def main():
    print(f"Running Aggregated Benchmarks ({ITERATIONS} iterations)...")
    print("---------------------------------------------------------")
    
    # Init pool
    init_pool()
    await init_valkey_cache()
    
    # Storage for results: { "Test Name": [duration1, duration2, ...] }
    agg_results = defaultdict(list)
    
    for i in range(ITERATIONS):
        print(f"Iteration {i+1}/{ITERATIONS}...", end=" ", flush=True)
        t0 = time.perf_counter()
        results = await run_iceberg_benchmarks()
        t1 = time.perf_counter()
        print(f"Done ({(t1-t0):.2f}s)")
        
        for r in results:
            agg_results[r.test_name].append(r.duration_ms)
            
    print("\n\n=== Final Aggregated Results (ms) ===")
    print(f"{'Test Name':<35} | {'Avg':<8} | {'Min':<8} | {'Max':<8} | {'P95':<8}")
    print("-" * 80)
    
    for name, durations in agg_results.items():
        # Filter out 0.0s (errors) if any, or keep them? 
        # If error, duration is 0.0. Let's warn if we see them.
        valid_durations = [d for d in durations if d > 0]
        if len(valid_durations) < len(durations):
            print(f"WARNING: {len(durations) - len(valid_durations)} errors in {name}")
        
        if not valid_durations:
            print(f"{name:<35} | {'ERROR':<8} | {'-':<8} | {'-':<8} | {'-':<8}")
            continue
            
        avg_val = statistics.mean(valid_durations)
        min_val = min(valid_durations)
        max_val = max(valid_durations)
        # Simple P95
        sorted_d = sorted(valid_durations)
        p95_idx = int(len(sorted_d) * 0.95)
        p95_val = sorted_d[p95_idx]
        
        print(f"{name:<35} | {avg_val:<8.2f} | {min_val:<8.2f} | {max_val:<8.2f} | {p95_val:<8.2f}")

if __name__ == "__main__":
    asyncio.run(main())

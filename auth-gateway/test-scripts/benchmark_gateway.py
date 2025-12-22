#!/usr/bin/env python3
"""
Performance benchmark for auth-gateway request processing.
Measures JWT validation, rate limiting, and authorization overhead.
"""

import os
import statistics
import time
from typing import Any

import requests


class GatewayBenchmark:
    def __init__(self, gateway_url: str, token: str) -> None:
        self.gateway_url = gateway_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def measure_request(self, endpoint: str, iterations: int = 100) -> dict[str, Any]:
        """Measure request latency over multiple iterations."""
        timings = []

        # Warm-up request (populate caches)
        requests.get(f"{self.gateway_url}{endpoint}", headers=self.headers, timeout=5)

        for _ in range(iterations):
            start = time.perf_counter()
            response = requests.get(
                f"{self.gateway_url}{endpoint}", headers=self.headers, timeout=5
            )
            end = time.perf_counter()

            elapsed_ms = (end - start) * 1000
            timings.append(elapsed_ms)

        return {
            "endpoint": endpoint,
            "status": response.status_code,
            "iterations": iterations,
            "min_ms": min(timings),
            "max_ms": max(timings),
            "mean_ms": statistics.mean(timings),
            "median_ms": statistics.median(timings),
            "p95_ms": statistics.quantiles(timings, n=20)[18],  # 95th percentile
            "p99_ms": statistics.quantiles(timings, n=100)[98],  # 99th percentile
        }

    def run_benchmarks(self) -> None:
        """Run comprehensive gateway performance benchmarks."""
        print("=" * 80)
        print("Auth Gateway Performance Benchmark")
        print("=" * 80)
        print()

        # Test different endpoints
        endpoints = [
            "/api/finance/reports",  # Requires auth + OpenFGA
            "/debug/healthz",  # Public endpoint (minimal overhead)
        ]

        for endpoint in endpoints:
            print(f"📊 Benchmarking: {endpoint}")
            print("-" * 80)

            result = self.measure_request(endpoint, iterations=100)

            print(f"Status Code:    {result['status']}")
            print(f"Iterations:     {result['iterations']}")
            print()
            print("Latency Statistics:")
            print(f"  Min:          {result['min_ms']:.2f} ms")
            print(f"  Max:          {result['max_ms']:.2f} ms")
            print(f"  Mean:         {result['mean_ms']:.2f} ms")
            print(f"  Median:       {result['median_ms']:.2f} ms")
            print(f"  P95:          {result['p95_ms']:.2f} ms")
            print(f"  P99:          {result['p99_ms']:.2f} ms")
            print()

        # Cache effectiveness test
        print("🔄 Testing Cache Effectiveness (Cold vs Warm)")
        print("-" * 80)

        # Clear OpenFGA cache by waiting 31 seconds
        endpoint = "/api/finance/reports"

        # Cold cache (first request after cache expiry)
        print("Waiting 31s for cache to expire...")
        time.sleep(31)

        start = time.perf_counter()
        requests.get(f"{self.gateway_url}{endpoint}", headers=self.headers, timeout=5)
        cold_time = (time.perf_counter() - start) * 1000

        # Warm cache (immediate subsequent request)
        start = time.perf_counter()
        requests.get(f"{self.gateway_url}{endpoint}", headers=self.headers, timeout=5)
        warm_time = (time.perf_counter() - start) * 1000

        print(f"Cold Cache (first request): {cold_time:.2f} ms")
        print(f"Warm Cache (cached):        {warm_time:.2f} ms")
        print(f"Cache Speedup:              {cold_time / warm_time:.2f}x faster")
        print()

        print("=" * 80)
        print("Summary")
        print("=" * 80)
        print()
        print("Gateway Overhead (authenticated endpoint with caching):")
        print(f"  Typical:  ~{result['median_ms']:.1f} ms")
        print(f"  P95:      ~{result['p95_ms']:.1f} ms")
        print()
        print("Breakdown (estimated):")
        print("  JWT Validation:        0.5-2 ms")
        print("  Rate Limiting (Redis): 1-3 ms")
        print("  OpenFGA Check (cached): 2-5 ms")
        print("  Network Overhead:      2-5 ms")
        print()
        print("💡 Tips for optimization:")
        print("  - Increase OpenFGA cache TTL for less critical paths")
        print("  - Use connection pooling (already enabled)")
        print("  - Consider in-process OpenFGA for ultra-low latency")
        print()


if __name__ == "__main__":
    # Get token
    if os.path.exists("test_token.txt"):
        with open("test_token.txt") as f:
            token = f.read().strip()
    else:
        print("❌ No token found! Run: python3 auth-gateway/setup-scripts/get_access_token.py")
        exit(1)

    benchmark = GatewayBenchmark("http://localhost:3000", token)
    benchmark.run_benchmarks()

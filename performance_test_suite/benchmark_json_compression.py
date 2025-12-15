"""
Benchmark script to test JSON serialization and compression performance.
"""

import json
import sys
import time
from pathlib import Path

import msgspec
import orjson
import zstandard as zstd

# Add src to path
sys.path.append(str(Path.cwd()))

# Sample data
sample_data = {
    "id": 1234,
    "user_id": 1,
    "event_type": "page_view",
    "page_url": "/test-page",
    "metadata": {
        "device": "desktop",
        "browser": "chrome",
        "duration": 45,
        "timestamp": "2024-12-11T10:00:00Z",
    },
    "created_at": "2024-12-11T10:00:00",
}

# Create 1000 records
records = [sample_data.copy() for _ in range(1000)]

print("=" * 70)
print("JSON SERIALIZATION BENCHMARKS")
print("=" * 70)

# Test 1: stdlib json
t0 = time.perf_counter()
for _ in range(100):
    json_result = json.dumps(records)
t1 = time.perf_counter()
json_time = (t1 - t0) * 10  # ms per 1000 records
json_size = len(json_result.encode())

print("\n1. Standard Library json.dumps():")
print(f"   Time: {json_time:.2f}ms")
print(f"   Size: {json_size:,} bytes")

# Test 2: orjson
t0 = time.perf_counter()
for _ in range(100):
    orjson_result = orjson.dumps(records)
t1 = time.perf_counter()
orjson_time = (t1 - t0) * 10
orjson_size = len(orjson_result)

print("\n2. orjson.dumps():")
print(f"   Time: {orjson_time:.2f}ms")
print(f"   Size: {orjson_size:,} bytes")
print(f"   Speedup: {json_time / orjson_time:.2f}x faster")

# Test 3: msgspec encoding
encoder = msgspec.json.Encoder()
t0 = time.perf_counter()
for _ in range(100):
    msgspec_result = encoder.encode(records)
t1 = time.perf_counter()
msgspec_time = (t1 - t0) * 10
msgspec_size = len(msgspec_result)

print("\n3. msgspec.json.Encoder():")
print(f"   Time: {msgspec_time:.2f}ms")
print(f"   Size: {msgspec_size:,} bytes")
print(f"   Speedup: {json_time / msgspec_time:.2f}x faster")

print("\n" + "=" * 70)
print("COMPRESSION BENCHMARKS")
print("=" * 70)

# Compression test
compressor = zstd.ZstdCompressor(level=3)
raw_data = orjson.dumps(records)

t0 = time.perf_counter()
for _ in range(100):
    compressed = compressor.compress(raw_data)
t1 = time.perf_counter()
compress_time = (t1 - t0) * 10

print("\nzstandard (level 3):")
print(f"   Raw size: {len(raw_data):,} bytes")
print(f"   Compressed: {len(compressed):,} bytes")
print(f"   Ratio: {len(raw_data) / len(compressed):.2f}x smaller")
print(f"   Compression time: {compress_time:.2f}ms")
print(f"   Throughput: {(len(raw_data) / 1024 / 1024) / (compress_time / 1000):.2f} MB/s")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("\nJSON Serialization (1000 records):")
print(f"  stdlib json:  {json_time:.2f}ms")
print(f"  orjson:       {orjson_time:.2f}ms ({json_time / orjson_time:.1f}x faster)")
print(f"  msgspec:      {msgspec_time:.2f}ms ({json_time / msgspec_time:.1f}x faster)")
print("\nCompression:")
print(f"  Raw:          {len(raw_data):,} bytes")
print(
    f"  Compressed:   {len(compressed):,} bytes ({len(raw_data) / len(compressed):.1f}x reduction)"
)
print(f"  Speed:        {compress_time:.2f}ms")

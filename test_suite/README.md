# Test Suite

This directory contains all testing, benchmarking, and profiling scripts for the performant Python application.

## 📂 Directory Contents

### Cache Testing
- **`test_cache.sh`** - Tests Redis LRU cache hit/miss scenarios
- **`test_decorator.sh`** - Compares manual vs decorator caching implementations
- **`test_redis_cache.py`** - Python-based cache testing (requires httpx)

### Performance Benchmarking
- **`benchmark.py`** - HTTP endpoint benchmarking with concurrent requests
- **`benchmark_uvloop.sh`** - uvloop performance benchmarks

### Profiling
- **`profile_app.sh`** - Application profiling with py-spy, Austin, and cProfile

## 🚀 Quick Start

### Run Cache Tests
```bash
cd test_suite
./test_cache.sh          # Test Redis cache functionality
./test_decorator.sh      # Compare caching patterns
```

### Run Benchmarks
```bash
cd test_suite
python benchmark.py      # Benchmark all endpoints
./benchmark_uvloop.sh    # Test event loop performance
```

### Profile Application
```bash
cd test_suite
./profile_app.sh         # Generate profiling reports
```

## 📊 Expected Results

### Cache Performance
- **Cache MISS**: ~800-1500ms (DuckDB processing)
- **Cache HIT**: ~5-10ms (Redis retrieval)
- **Speedup**: 100-150x for hot data

### Endpoint Benchmarks
- **Standard (Pydantic)**: Baseline performance
- **Optimized (msgspec)**: 10-20% faster
- **DuckDB**: SQL-based processing

## 🔧 Prerequisites

Make sure the application is running:
```bash
docker-compose up -d
```

For Python tests, install dependencies:
```bash
pip install httpx
```

## 📝 Notes

All test scripts assume the application is running on `http://localhost:8080`.
Adjust `BASE_URL` in scripts if using a different port.

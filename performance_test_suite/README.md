# Performance Test Suite

This directory contains comprehensive benchmarking, profiling, and quality assurance tools for the Performant Python application.

## 🛠️ Code Quality & Pre-Commit

We maintain high code standards using a consolidated pre-commit script. This ensures all code is formatted, typed, secure, and tested before merging.

### Running Checks
```bash
# Run all checks (Ruff, MyPy, Refurb, Bandit, Pytest)
../pre_commit_check.sh

# Run full Bandit scan (all folders)
../pre_commit_check.sh --bandit-all

# Run checks on specific folder
../pre_commit_check.sh --bandit-folders performance_test_suite/
```

### Checks Included
- **Ruff**: Linting and formatting
- **MyPy**: Static type checking (Strict mode)
- **Refurb**: Modern Python idiom analysis
- **Bandit**: Security vulnerability scanning
- **Pytest**: Functional testing with **80% coverage enforcement**

---

## 📂 Directory Contents

### 🧊 Iceberg & Data Benchmarks
- **`iceberg_runner.py`**: Benchmarks DuckDB queries on Iceberg tables (S3) with varying complexities.
- **`iceberg_join_example.py`**: Demonstrates and benchmarks joining Iceberg tables with internal DuckDB tables.
- **`check_metadata_scan.py`**: Verifies performance of direct metadata file scanning.
- **`check_optimizations.py`**: Validates specific query optimizations (partition pruning, projection pushdown).
- **`check_parquet_performance.py`**: Compares raw Parquet vs Iceberg reading performance.

### ⚡ Concurrency & Memory
- **`duckdb_concurrency.py`**: Stress tests DuckDB with concurrent connections/threads.
- **`benchmark_memory.py`**: Profiles memory usage of Pydantic vs msgspec vs Polars.
- **`benchmark_json_compression.py`**: Compares JSON serialization sizes and Zstd compression ratios.

### 🌐 HTTP & App Benchmarks
- **`benchmark.py`**: Standard HTTP endpoint load testing.
- **`benchmark_pydantic_vs_msgspec.py`**: Direct comparison of validation libraries.
- **`test_valkey_cache.sh`**: Validates Valkey LRU caching behavior.

---

## 🚀 Running Benchmarks

**Note**: All commands use `uv` for fast, reproducible execution.

### 1. HTTP Load Test
```bash
uv run performance_test_suite/benchmark.py
```

### 2. DuckDB Iceberg Performance
```bash
# Run the full suite of Iceberg queries
uv run performance_test_suite/iceberg_runner.py
```

### 3. Memory Profiling
```bash
# Compare memory footprint of different libraries
uv run performance_test_suite/benchmark_memory.py
```

### 4. Concurrency Stress Test
```bash
# Test DuckDB under load (30 concurrent queries)
uv run performance_test_suite/duckdb_concurrency.py
```

---

## 📊 Performance Baselines

| Benchmark | Tool/Metric | Optimized Result | Baseline/Node.js |
|-----------|-------------|------------------|------------------|
| **Cache Hit** | Valkey (C) | **~2ms** | ~500ms (Uncached) |
| **Serialization** | msgspec (C) | **20x faster** | Pydantic V2 |
| **Iceberg Scan** | DuckDB (C++) | **<300ms** (10M rows) | >2s (Standard) |
| **Full Text Search** | Tantivy (Rust) | **~4ms** (10k docs) | ~15ms (Postgres) |
| **JSON Size** | Zstandard | **30% smaller** | Gzip |

## 🔧 Prerequisites

Ensure the application stack is running:
```bash
docker compose up -d
```

Install dependencies:
```bash
uv sync
```

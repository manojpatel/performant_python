# High-Performance Python Backend

A production-ready, ultra-high-performance Python backend stack leveraging Rust/C/C++ libraries to achieve **90% of Node.js performance** while maintaining Python's **unmatched AI/ML ecosystem dominance**.

## ⚡ The Stack

### Core Web
- **Server**: [Granian 1.6+](https://github.com/emmett-framework/granian) - Rust HTTP server
- **Framework**: [FastAPI 0.115+](https://fastapi.tiangolo.com/) - Modern async web framework
- **Event Loop**: [uvloop 0.21+](https://github.com/MagicStack/uvloop) - Ultra-fast asyncio (C/libuv)

### Data & Processing
- **Database**: [PostgreSQL 17](https://postgresql.org/) - Production relational database
- **Caching**: [Valkey 8.0](https://valkey.io/) - High-performance Redis fork (C)
- **DataFrames**: [Polars 1.17+](https://pola.rs/) - Lightning-fast dataframes (Rust)
- **SQL/OLAP**: [DuckDB 1.1.3](https://duckdb.org/) - Analytics SQL engine (C++)
- **Arrays**: [NumPy 2.2](https://numpy.org/) - Numerical computing

### Validation & Serialization
- **Validation**: [Pydantic 2.10](https://docs.pydantic.dev/) - Rust-powered validation
- **Ultra-fast**: [msgspec 0.18](https://github.com/jcrist/msgspec) - C/Cython validation
- **JSON**: [orjson 3.10](https://github.com/ijl/orjson) - Fastest JSON library (Rust)

### Search, Rendering & Performance
- **Search**: [Tantivy 0.22](https://github.com/quickwit-oss/tantivy-py) - Full-text search (Rust)
- **Templates**: [MiniJinja 2.4](https://github.com/mitsuhiko/minijinja) - Fast templates (Rust)
- **Compression**: [zstandard 0.23](https://github.com/indygreg/python-zstandard) - Fast HTTP compression
- **Hashing**: [xxhash 3.5](https://github.com/ifduyue/python-xxhash) - Ultra-fast cache keys

## 🚀 Quick Start

```bash
# Start all services (app + Valkey + observability)
docker-compose up -d

# View logs
docker-compose logs -f performant-python-app

# Run tests
cd performance_test_suite && ./test_valkey_cache.sh
```

**Service URLs:**
- **Application**: http://localhost:8080
- **PostgreSQL**: localhost:5432 (production database)
- **Jaeger UI**: http://localhost:16686 (distributed tracing)
- **OpenSearch**: http://localhost:9200 (trace storage)
- **Valkey**: localhost:6379 (cache)

## 📂 Project Structure

```
performant_python/
├── src/                           # Application code
│   ├── main.py                    # FastAPI app entry point
│   ├── lib/                       # Core libraries
│   │   ├── valkey_cache.py        # Valkey caching decorator (xxhash keys)
│   │   ├── duckdb_client.py       # DuckDB connection pool
│   │   └── postgres_client.py     # PostgreSQL asyncpg client
│   ├── middleware/                # Middleware components
│   │   ├── compression.py         # Zstandard compression
│   │   └── telemetry.py           # OpenTelemetry tracing
│   ├── samples/                   # Demo/test/benchmark endpoints
│   │   ├── samples_routes.py      # All sample API routes
│   │   ├── services.py            # Business logic (Polars, DuckDB)
│   │   ├── pydantic_models.py     # Pydantic models
│   │   ├── msgspec_models.py      # msgspec models (faster)
│   │   ├── extras.py              # Search & templating (Tantivy, MiniJinja)
│   │   ├── pg_pydantic_dict.py    # PostgreSQL production endpoints
│   │   ├── pg_polars_benchmark.py # Pydantic + Polars benchmarks
│   │   ├── pg_polars_msgspec.py   # msgspec + Polars benchmarks
│   │   └── pg_duckdb_comparison.py # PostgreSQL vs DuckDB comparison
│   └── routes/                    # Additional route modules
├── performance_test_suite/        # All tests & benchmarks
│   ├── test_valkey_cache.sh       # Valkey cache validation
│   ├── test_valkey_cache.py       # Python cache tests
│   ├── test_decorator.sh          # Caching pattern comparison
│   ├── benchmark.py               # HTTP benchmarking
│   └── profile_app.sh             # Performance profiling
├── logs/                          # Application logs
├── db/                            # Database files
├── docker-compose.yml             # Service orchestration
├── Dockerfile                     # Application container
├── requirements.txt               # Python dependencies
├── PERFORMANCE_COMPARISON.md      # Detailed benchmarks
└── ADDITIONAL_BENCHMARKS.md       # PostgreSQL & msgspec metrics
```

## 🌐 API Endpoints

### Production Endpoints (PostgreSQL)
- **`POST /samples/events`** - Create user event
- **`GET /samples/events/{user_id}`** - Get user events with pagination
- **`POST /samples/events/bulk`** - Bulk insert events for testing
- **`GET /samples/analytics/summary`** - Analytics summary (PostgreSQL aggregations)
- **`GET /samples/analytics/conversion-funnel`** - Conversion funnel metrics

### Caching Demonstrations
- **`GET /samples/duckdb-cached`** - Valkey LRU cache with detailed timing metrics
- **`GET /samples/duckdb-cached-decorator`** - Same using `@valkey_cache` decorator

### Data Processing & Benchmarks
- **`POST /samples/batch`** - Pydantic validation + Polars DataFrames
- **`POST /samples/batch-msgspec`** - msgspec validation (3-5x faster)
- **`POST /samples/duckdb`** - DuckDB SQL aggregations
- **`GET /samples/pg/benchmark`** - PostgreSQL + Polars benchmarks
- **`GET /samples/pg/benchmark-all`** - Compare all PostgreSQL approaches
- **`GET /samples/pg/duckdb-compare`** - PostgreSQL vs DuckDB analytics

### Other Features
- **`GET /`** - Health check / API info
- **`GET /samples/`** - Sample routes root
- **`GET /samples/search?q=query`** - Full-text search (Tantivy)
- **`POST /samples/render`** - HTML rendering (MiniJinja)
- **`GET /samples/benchmark/{size}`** - Dataset generation benchmark
- **`GET /samples/large-json`** - Large JSON response test

## 📊 Performance

**Key Results:**
- 🚀 **250x faster** with Valkey cache (517ms → 2.1ms)
- ⚡ **10x faster hashing** with xxhash vs SHA256
- 📦 **20-30% better compression** with zstandard vs gzip
- 🤖 **100:1 AI/ML advantage** over Node.js ecosystem

**Benchmark Results (Dec 2024):**
```
50,000 records processed:      294ms total (50ms Polars)
PostgreSQL analytics (7.2K):   29.5ms average  
PostgreSQL bulk inserts:       26K inserts/second
Cache hit response:            2.1ms (Valkey)
Search 10k documents:          4.4ms (Tantivy)
msgspec validation:            20x faster than Pydantic
```

**📈 See [PERFORMANCE_COMPARISON.md](PERFORMANCE_COMPARISON.md) for:**
- Detailed Python vs Node.js vs Rust benchmarks
- Library-by-library performance analysis  
- AI/ML ecosystem comparison
- Real-world use case recommendations

## 🧪 Testing

All test scripts in `performance_test_suite/`:

```bash
cd performance_test_suite

# Test Valkey cache (hit/miss scenarios)
./test_valkey_cache.sh
# Or use Python version (requires: pip install httpx)
python test_valkey_cache.py

# Compare manual vs decorator caching
./test_decorator.sh

# Benchmark all endpoints
python benchmark.py

# Profile application
./profile_app.sh
```

## 🎯 Key Features

###  1. Valkey LRU Caching with xxhash
```python
from src.lib.valkey_cache import valkey_cache

@valkey_cache(ttl=300, key_prefix="user_data")
async def get_user_data(user_id: int):
    """Automatically cached for 5 minutes with xxhash keys"""
    return await fetch_from_db(user_id)
```

### 2. DuckDB Connection Pooling
```python
from src.lib.duckdb_client import get_pool

async def query_data():
    pool = get_pool()
    async with pool.connection() as conn:
        result = conn.execute("SELECT * FROM data").fetchall()
    return result
```

### 3. PostgreSQL with asyncpg
```python
from src.lib.postgres_client import get_postgres

async def query_events(user_id: int, limit: int = 100):
    """Query PostgreSQL with asyncpg (3x faster than psycopg)"""
    pool = await get_postgres()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM user_events WHERE user_id = $1 LIMIT $2",
            user_id, limit
        )
    return rows
```

### 4. Polars DataFrames
```python
import polars as pl

df = pl.DataFrame(data)
stats = df.group_by("category").agg([
    pl.mean("value").alias("avg"),
    pl.max("value").alias("max")
])
```

## 📈 Why Python Over Node.js?

### **AI/ML Dominance (100:1 Advantage)**
```
Python: PyTorch, TensorFlow, LangChain, Transformers, scikit-learn
Node.js: TensorFlow.js (limited), ONNX Runtime (inference only)
Rust: Growing but immature ecosystem
```

### **This Stack Closes the Performance Gap**
- **90% of Node.js speed** with optimized libraries
- **100:1 AI/ML ecosystem advantage** 
- **Python syntax & productivity**
- **Rust/C/C++ performance** under the hood

### **Best of Both Worlds**
```
┌─────────────────────┐
│ Python (Business)   │  ← Productivity
├─────────────────────┤
│ Rust/C++ Libraries  │  ← Performance
└─────────────────────┘
```

## 📊 Observability

Minimal observability stack:
- **Jaeger UI**: http://localhost:16686 - Trace visualization
- **OpenSearch**: http://localhost:9200 - Trace persistence

All endpoints automatically instrumented with OpenTelemetry.

## 🚀 Production Deployment

### Environment Variables
```bash
ENABLE_TRACING=true                           # Toggle tracing
OTEL_SERVICE_NAME=performant-python          # Service name
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317  # Trace endpoint
VALKEY_URL=valkey://valkey:6379              # Valkey connection
```

### Scaling
```bash
# In entrypoint.sh, increase workers:
granian --workers 4 --loop uvloop src.main:app
```

### Production Checklist
- [ ] Configure Valkey persistence (RDB/AOF)
- [ ] Set up Valkey Sentinel/Cluster for HA
- [ ] Monitor cache hit ratios
- [ ] Scale workers based on CPU cores
- [ ] Implement cache warming
- [ ] Tune zstandard compression level
- [ ] Set up proper logging aggregation

## 📝 Code Highlights

- **`src/main.py`**: FastAPI app with uvloop, Valkey, PostgreSQL initialization, compression
- **`src/lib/valkey_cache.py`**: Generic `@valkey_cache` decorator with xxhash keys
- **`src/lib/postgres_client.py`**: asyncpg connection pool management
- **`src/lib/duckdb_client.py`**: Thread-safe DuckDB connection pooling
- **`src/middleware/compression.py`**: Zstandard HTTP compression middleware
- **`src/middleware/telemetry.py`**: OpenTelemetry instrumentation
- **`src/samples/services.py`**: Polars & DuckDB processing with caching patterns
- **`src/samples/extras.py`**: Tantivy search & MiniJinja templating
- **`src/samples/pg_*.py`**: PostgreSQL benchmarks and production examples

## 🔧 Development

### Local Setup (without Docker)
```bash
# Install uv (fast package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv and install deps
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Run server
granian --interface asgi --reload src.main:app
```

### Library Versions
All libraries are latest stable versions (December 2024):
- Polars 1.17, DuckDB 1.1.3, NumPy 2.2, Valkey 6.0
- zstandard 0.23, xxhash 3.5, orjson 3.10
- See `requirements.txt` for complete list

## 🎓 Learn More

- **[PERFORMANCE_COMPARISON.md](PERFORMANCE_COMPARISON.md)** - Detailed Python vs Node.js vs Rust benchmarks
- **[ADDITIONAL_BENCHMARKS.md](ADDITIONAL_BENCHMARKS.md)** - PostgreSQL metrics, msgspec benchmarks
- **[performance_test_suite/README.md](performance_test_suite/README.md)** - Complete testing guide

## 📄 License

MIT License - feel free to use for your projects!

---

**Built to demonstrate that Python can be blazingly fast while maintaining its AI/ML supremacy.** 🚀

---

## 📜 Logging & Correlation Guide

This project includes a production-grade logging and tracing setup.

### 1. How to Log
Use the `logger` instance. The syntax is `logger.info(event_name, **kwargs)`.

```python
logger.info("payment_processed", user_id=42, amount=100.50, currency="USD")
```

### 2. Special Keywords
*   **`event` (Positional Argument 1)**: This is the **name** of the log event. It is mandatory.
    *   *In Logs*: Appears as `"event": "payment_processed"`.
    *   *In Jaeger*: Appears as the **Name** of the Span Event.
*   **`timestamp` (Automatic)**: Added automatically by the system.
    *   *In Jaeger*: Used to correctly position the event on the timeline.

### 3. Correlation with Jaeger
If Tracing is **ENABLED** (`ENABLE_TRACING=true`):
*   **Automatic**: Every log you write is automatically attached to the current active Trace Span.
*   **Trace ID**: The log in `stdout` will automatically contain `trace_id` and `span_id`.
*   **Visualization**: Open Jaeger, find the trace, and look for "Logs" (Events) on the span.

### 4. Correlation without Tracing (Fallback)
If Tracing is **DISABLED** (or sampled out):
*   **Request ID**: A unique `request_id` (UUID) is automatically generated for every request.
*   **Persistence**: This ID is present in **every log line** (`"request_id": "..."`).
*   **Usage**: Copy the `request_id` from one log and grep for it to see the full request history.
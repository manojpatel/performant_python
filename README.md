# High-Performance Python Backend

A production-ready, ultra-high-performance Python backend stack leveraging Rust/C/C++ libraries to achieve **90% of Node.js performance** while maintaining Python's **unmatched AI/ML ecosystem dominance**.

## ⚡ The Stack

### Core Web
- **Server**: [Granian 1.6+](https://github.com/emmett-framework/granian) - Rust HTTP server
- **Framework**: [FastAPI 0.115+](https://fastapi.tiangolo.com/) - Modern async web framework
- **Event Loop**: [uvloop 0.21+](https://github.com/MagicStack/uvloop) - Ultra-fast asyncio (C/libuv)

### Data & Processing
- **Caching**: [Redis 5.2](https://redis.io/) - In-memory LRU cache (C)
- **DataFrames**: [Polars 1.36+](https://pola.rs/) - Lightning-fast dataframes (Rust)
- **SQL/OLAP**: [DuckDB 1.1.3](https://duckdb.org/) - Analytics SQL engine (C++)
- **Arrays**: [NumPy 2.2](https://numpy.org/) - Numerical computing

### Validation & Serialization
- **Validation**: [Pydantic 2.10](https://docs.pydantic.dev/) - Rust-powered validation
- **Ultra-fast**: [msgspec 0.18](https://github.com/jcrist/msgspec) - C/Cython validation
- **JSON**: [orjson 3.10](https://github.com/ijl/orjson) - Fastest JSON library (Rust)

### Search & Rendering
- **Search**: [Tantivy 0.22](https://github.com/quickwit-oss/tantivy-py) - Full-text search (Rust)
- **Templates**: [MiniJinja 2.4](https://github.com/mitsuhiko/minijinja) - Fast templates (Rust)

## 🚀 Quick Start

```bash
# Start all services (app + Redis + observability)
docker-compose up -d

# View logs
docker-compose logs -f performant-python-app

# Run tests
cd test_suite && ./test_cache.sh
```

**Service URLs:**
- **Application**: http://localhost:8080
- **Jaeger UI**: http://localhost:16686 (distributed tracing)
- **OpenSearch**: http://localhost:9200 (trace storage)

## 📂 Project Structure

```
performant_python/
├── src/                    # Application code
│   ├── main.py            # FastAPI app & endpoints
│   ├── services.py        # Business logic (Polars, DuckDB)
│   ├── redis_cache.py     # Redis caching decorator
│   ├── database.py        # DuckDB connection pool
│   ├── models.py          # Pydantic models
│   ├── fast_models.py     # msgspec models (faster)
│   ├── extras.py          # Search & templating
│   └── telemetry.py       # OpenTelemetry tracing
├── test_suite/            # All tests & benchmarks
│   ├── test_cache.sh      # Redis cache validation
│   ├── test_decorator.sh  # Caching pattern comparison
│   ├── benchmark.py       # HTTP benchmarking
│   └── profile_app.sh     # Performance profiling
├── logs/                  # Application logs
├── docker-compose.yml     # Service orchestration
├── Dockerfile            # Application container
└── requirements.txt      # Python dependencies
```

## 🌐 API Endpoints

### Caching Demonstrations
- **`POST /duckdb-cached`** - Redis LRU cache with detailed timing metrics
- **`POST /duckdb-cached-decorator`** - Same using `@redis_cache` decorator

### Data Processing
- **`POST /process`** - Pydantic validation + Polars DataFrames
- **`POST /process-msgspec`** - msgspec validation (3-5x faster)
- **`POST /duckdb`** - DuckDB SQL aggregations

### Other Features
- **`GET /`** - Hello World
- **`GET /search?q=query`** - Full-text search (Tantivy)
- **`POST /render`** - HTML rendering (MiniJinja)
- **`GET /benchmark/{size}`** - Internal benchmark

## 📊 Performance

**Key Results:**
- 🚀 **1,096x faster** with Redis cache (2.5s → 2.3ms)
- ⚡ **90% of Node.js speed** for web requests (58K vs 65K req/s)
- 🤖 **100:1 AI/ML advantage** over Node.js ecosystem

**Why This Stack?**
```
Traditional Python (Flask):    8.5K req/s
This Stack (Granian+Rust):    58K req/s  ← 7x faster
Node.js (Fastify):            65K req/s
Rust (Actix):                180K req/s
```

**📈 See [PERFORMANCE_COMPARISON.md](PERFORMANCE_COMPARISON.md) for:**
- Detailed Python vs Node.js vs Rust benchmarks
- Library-by-library performance analysis  
- AI/ML ecosystem comparison
- Real-world use case recommendations

## 🧪 Testing

All test scripts in `test_suite/`:

```bash
cd test_suite

# Test Redis cache (hit/miss scenarios)
./test_cache.sh

# Compare manual vs decorator caching
./test_decorator.sh

# Benchmark all endpoints
python benchmark.py

# Profile application
./profile_app.sh
```

## 🎯 Key Features

### 1. Redis LRU Caching
```python
from src.redis_cache import redis_cache

@redis_cache(ttl=300, key_prefix="user_data")
async def get_user_data(user_id: int):
    """Automatically cached for 5 minutes"""
    return await fetch_from_db(user_id)
```

### 2. DuckDB Connection Pooling
```python
from src.database import get_pool

async def query_data():
    pool = get_pool()
    async with pool.connection() as conn:
        result = conn.execute("SELECT * FROM data").fetchall()
    return result
```

### 3. Polars DataFrames
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
REDIS_URL=redis://redis:6379                 # Redis connection
```

### Scaling
```bash
# In entrypoint.sh, increase workers:
granian --workers 4 --loop uvloop src.main:app
```

### Production Checklist
- [ ] Configure Redis persistence (RDB/AOF)
- [ ] Set up Redis Sentinel for HA
- [ ] Monitor cache hit ratios
- [ ] Scale workers based on CPU cores
- [ ] Implement cache warming
- [ ] Set up proper logging aggregation

## 📝 Code Highlights

- **`src/main.py`**: FastAPI app with uvloop, Redis initialization, all endpoints
- **`src/redis_cache.py`**: Generic `@redis_cache` decorator for any async function
- **`src/services.py`**: Polars & DuckDB processing with caching patterns
- **`src/database.py`**: Thread-safe DuckDB connection pooling
- **`src/extras.py`**: Tantivy search & MiniJinja templating

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
- Polars 1.36, DuckDB 1.1.3, NumPy 2.2, Redis 5.2
- See `requirements.txt` for complete list

## 🎓 Learn More

- **[PERFORMANCE_COMPARISON.md](PERFORMANCE_COMPARISON.md)** - Detailed Python vs Node.js vs Rust benchmarks
- **[test_suite/README.md](test_suite/README.md)** - Complete testing guide
- **Artifacts** - Implementation plans, walkthroughs, caching patterns

## 📄 License

MIT License - feel free to use for your projects!

---

**Built to demonstrate that Python can be blazingly fast while maintaining its AI/ML supremacy.** 🚀
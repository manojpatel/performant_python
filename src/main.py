from fastapi import FastAPI, Body, Request
from fastapi.responses import ORJSONResponse, Response, HTMLResponse
from contextlib import asynccontextmanager
import time
import msgspec

from src.models import BatchData, ProcessingStats, DataPoint
from src.fast_models import FastBatchData, FastProcessingStats
from src.services import process_data_batch, generate_large_dataset, process_with_duckdb, get_batch_stats_cached, get_batch_stats_with_decorator
from src.extras import render_report, SearchEngine
from src.telemetry import init_tracing, instrument_fastapi

# Initialize OpenTelemetry tracing BEFORE creating the app
init_tracing()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load resources or models here
    print("🚀 application starting up...")
    
    # Initialize Redis cache
    from src.redis_cache import init_cache
    await init_cache()
    print("🔴 Redis cache initialized")
    
    # Initialize DuckDB connection pool
    from src.database import init_pool
    init_pool(database=":memory:", pool_size=4)
    print("💾 DuckDB connection pool initialized (4 connections)")
    
    # Init Search Index
    # Run in a separate thread to avoid blocking the asyncio event loop
    import asyncio
    print("🔎 Seeding search index...")
    await asyncio.to_thread(SearchEngine.get_instance().seed, 10000) 
    
    yield
    
    # Cleanup
    from src.redis_cache import get_cache
    await get_cache().close()
    print("🛑 application shutting down...")

app = FastAPI(
    title="Performant Python Demo",
    default_response_class=ORJSONResponse, # Use orjson by default for all endpoints
    lifespan=lifespan
)

# Instrument FastAPI for tracing
instrument_fastapi(app)

@app.get("/")
async def root():
    """
    Simple baseline endpoint.
    """
    return {"message": "Hello from High-Performance Python!", "backend": "Granian + FastAPI + Rust/C++"}

@app.get("/search")
async def search(q: str, limit: int = 10):
    """
    Searches the in-memory index using Tantivy (Rust).
    """
    t0 = time.perf_counter()
    # Get the singleton instance
    engine = SearchEngine.get_instance()
    results = engine.search(q, limit)
    t1 = time.perf_counter()
    return {
        "query": q,
        "hits": len(results),
        "duration_ms": (t1 - t0) * 1000,
        "results": results
    }

@app.post("/render", response_class=HTMLResponse)
async def render_html(stats: ProcessingStats):
    """
    Renders a report HTML using MiniJinja (Rust).
    Accepts the stats object and returns formatted HTML.
    """
    t0 = time.perf_counter()
    # Convert Pydantic model to dict for template context
    context = stats.model_dump()
    
    # Add some timing info to context
    context["duration_ms"] = 123.45 # Dummy value for template
    
    html = render_report(context)
    t1 = time.perf_counter()
    
    # Add a custom header to see render time
    return HTMLResponse(content=html, headers={"X-Render-Time-Ms": str((t1 - t0) * 1000)})

@app.post("/process", response_model=ProcessingStats)
async def process_batch(data: BatchData):
    """
    Validates data using Pydantic v2, processes using Polars (Rust).
    Demonstrates fastest path for structured batch processing.
    """
    # Convert Pydantic models to list of dicts for Polars
    # model_dump() is the new v2 method (faster than dict())
    raw_data = [d.model_dump() for d in data.data]
    
    stats = await process_data_batch(data.batch_id, raw_data)
    return stats

@app.post("/process-msgspec", response_model=ProcessingStats)
async def process_batch_msgspec(request: Request):
    """
    Uses msgspec for validation and deserialization (faster than Pydantic).
    Returns a raw JSON response (bytes) to skip FastAPI's serialization overhead.
    """
    body = await request.body()
    
    # 1. Validation & Deserialization (msgspec is very fast here)
    try:
        payload = msgspec.json.decode(body, type=FastBatchData)
    except msgspec.ValidationError as e:
        return Response(content=str(e), status_code=422)
    
    # 2. Process (Convert msgspec structs to dicts for Polars if needed, or use directly)
    # Polars can accept list of objects if they are compatible, but dicts are safer
    # msgspec.structs.asdict is fast
    raw_data = [msgspec.structs.asdict(d) for d in payload.data]
    
    # Reuse the logic (in a real app, we'd optimize the service to take structs directly)
    stats_pydantic = process_data_batch(payload.batch_id, raw_data)
    
    # 3. Serialize output using msgspec
    # Convert pydantic result back to msgspec struct or just dict
    fast_stats = FastProcessingStats(
        batch_id=stats_pydantic.batch_id,
        processed_at=stats_pydantic.processed_at.timestamp(),
        total_records=stats_pydantic.total_records,
        mean_value=stats_pydantic.mean_value,
        max_value=stats_pydantic.max_value,
        by_category=stats_pydantic.by_category,
        processing_speed_score=stats_pydantic.total_records * 1.5
    )
    
    json_bytes = msgspec.json.encode(fast_stats)
    return Response(content=json_bytes, media_type="application/json")

@app.post("/duckdb")
async def duckdb_processing(data: BatchData):
    """Uses DuckDB (C++ OLAP engine) for SQL-based analytics (async with connection pooling)."""
    raw_data = [d.model_dump() for d in data.data]
    result = process_with_duckdb(data.batch_id, raw_data)
    return result

@app.post("/duckdb-cached")
async def duckdb_cached_processing(data: BatchData):
    """
    Demonstrates Redis LRU cache → DuckDB fallback pattern.
    
    Flow:
    1. Check Redis cache first (sub-millisecond lookup)
    2. If cache HIT: return immediately from Redis
    3. If cache MISS: query DuckDB (simulating S3 Parquet), cache result, return
    
    This simulates a production pattern where:
    - Hot data is served from Redis (ultra-fast)
    - Cold data is fetched from S3 via DuckDB (fast SQL over Parquet)
    - Results are cached with 5-minute TTL
    
    Response includes timing metrics to demonstrate cache performance.
    
    IMPLEMENTATION: Manual caching with detailed timing breakdown.
    """
    raw_data = [d.model_dump() for d in data.data]
    result = await get_batch_stats_cached(data.batch_id, raw_data)
    return result

@app.post("/duckdb-cached-decorator")
async def duckdb_cached_decorator(data: BatchData):
    """
    Same as /duckdb-cached but using the @redis_cache decorator.
    
    Demonstrates the generic caching decorator pattern:
    - Cleaner code (no manual cache logic in function)
    - Automatic cache key generation from arguments
    - Standardized response format with cache metadata
    - Reusable pattern for any async function
    
    Compare this endpoint with /duckdb-cached to see the difference between:
    - Manual implementation (more control, detailed metrics)
    - Decorator pattern (cleaner, less boilerplate)
    
    IMPLEMENTATION: Using @redis_cache decorator.
    """
    raw_data = [d.model_dump() for d in data.data]
    result = await get_batch_stats_with_decorator(data.batch_id, raw_data)
    return result


@app.get("/benchmark/{size}")
async def benchmark(size: int):
    """
    Generates data and processes it through Polars (async).
    This endpoint demonstrates Polars' performance for large datasets.
    Avoids HTTP overhead of sending large JSON bodies for testing logic speed.
    """
    t0 = time.perf_counter()
    raw_data = await generate_large_dataset(size)
    t1 = time.perf_counter()
    
    stats = await process_data_batch(f"bench-{size}", raw_data)
    t2 = time.perf_counter()
    
    return {
        "generation_time_ms": (t1 - t0) * 1000,
        "processing_time_ms": (t2 - t1) * 1000,
        "total_time_ms": (t2 - t0) * 1000,
        "stats": stats
    }

@app.get("/large-json")
async def large_json():
    """
    Returns a large JSON payload to demonstrate ORJSON serialization speed.
    """
    data = generate_large_dataset(5000)
    return {"count": len(data), "data": data}

if __name__ == "__main__":
    # This block allows running the script directly, but using the CLI is recommended
    import granian
    print("Starting Granian server via python script...")
    granian.Granian(
        target="src.main:app",
        address="0.0.0.0",
        port=8080,
        interface="asgi",
        workers=1,
        threads=1
    ).serve()

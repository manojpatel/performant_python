"""
Sample Routes - All testing and demonstration endpoints
Framework capabilities, benchmarks, and experimental features
"""
from fastapi import APIRouter, Body
from fastapi.responses import HTMLResponse, Response
from typing import List
import time
import msgspec

from src.samples.pydantic_models import BatchData, ProcessingStats, UserEvent, UserEventResponse, AnalyticsSummary, ConversionFunnel
from src.samples.services import process_data_batch, generate_large_dataset, process_with_duckdb, get_batch_stats_cached, get_batch_stats_with_decorator
from src.samples.extras import render_report, SearchEngine

# Create router for all sample/test endpoints
router = APIRouter(tags=["Samples & Testing"])


# =============================================================================
# Framework Demonstration Routes
# =============================================================================

@router.get("/")
async def sample_root():
    """Sample root endpoint - demonstrates basic FastAPI + ORJSON."""
    return {"message": "Sample routes for testing framework capabilities"}


@router.get("/search")
async def search(q: str, limit: int = 10):
    """
    Searches the in-memory index using Tantivy (Rust).
    Demonstrates: Rust integration, in-memory indexing
    """
    t0 = time.perf_counter()
    engine = SearchEngine.get_instance()
    results = engine.search(q, limit)
    t1 = time.perf_counter()
    return {
        "query": q,
        "hits": len(results),
        "duration_ms": (t1 - t0) * 1000,
        "results": results
    }


@router.post("/render", response_class=HTMLResponse)
async def render_html(stats: ProcessingStats):
    """
    Renders a report HTML using MiniJinja (Rust).
    Demonstrates: Template rendering with Rust-based MiniJinja
    """
    t0 = time.perf_counter()
    html = render_report(stats.model_dump())
    t1 = time.perf_counter()
    return Response(
        content=html,
        media_type="text/html",
        headers={"X-Render-Time-Ms": str((t1 - t0) * 1000)}
    )


# =============================================================================
# DuckDB & Polars Demonstration
# =============================================================================

@router.post("/batch")
async def batch_processing(batch: BatchData) -> ProcessingStats:
    """
    Process data batch with Polars + DuckDB.
    Demonstrates: Polars DataFrames, DuckDB in-memory analytics
    """
    return await process_data_batch(batch.batch_id, batch.data)


@router.post("/batch-msgspec")
async def batch_processing_msgspec(batch: BatchData = Body(...)):
    """
    Process data batch using msgspec internally (faster validation).
    Demonstrates: msgspec for 3-5x faster validation than Pydantic
    Note: Input uses Pydantic for FastAPI compatibility, msgspec used internally
    """
    from src.samples.msgspec_models import FastProcessingStats
    raw_data = [d.model_dump() for d in batch.data]
    stats = await process_data_batch(raw_data)
    # Return dict for JSON serialization
    result = FastProcessingStats(**stats.model_dump())
    return msgspec.structs.asdict(result)


@router.post("/duckdb")
async def duckdb_processing(batch: BatchData):
    """
    Process data using DuckDB SQL.
    Demonstrates: DuckDB SQL engine for OLAP queries
    """
    return await process_with_duckdb(batch.batch_id, batch.data)


@router.get("/duckdb-cached")
async def duckdb_cached_endpoint(batch_id: str, size: int = 100):
    """
    DuckDB processing with Valkey caching (manual logic).
    Demonstrates: Valkey caching, xxhash cache keys, zstandard compression
    """
    data = await generate_large_dataset(size)
    return await get_batch_stats_cached(batch_id, data)


@router.get("/duckdb-cached-decorator")
async def duckdb_decorator_endpoint(batch_id: str, size: int = 100):
    """
    DuckDB processing with @valkey_cache decorator.
    Demonstrates: Decorator-based caching with Valkey
    """
    data = await generate_large_dataset(size)
    return await get_batch_stats_with_decorator(batch_id, data)


@router.get("/benchmark/{size}")
async def benchmark_endpoint(size: int):
    """
    Generate large dataset and benchmark serialization.
    Demonstrates: ORJSON serialization performance
    """
    t0 = time.perf_counter()
    data = await generate_large_dataset(size)
    t1 = time.perf_counter()
    return {
        "size": size,
        "records": len(data),
        "generation_time_ms": (t1 - t0) * 1000,
        "sample": data[:3] if data else []
    }


@router.get("/large-json")
async def large_json_response():
    """
    Generate large JSON response to test serialization.
    Demonstrates: ORJSON performance with large payloads
    """
    data = await generate_large_dataset(10000)
    return {"count": len(data), "data": data}


# =============================================================================
# PostgreSQL Benchmarks
# =============================================================================

@router.get("/pg/benchmark")
async def benchmark_postgres_polars(user_id: int = 1, limit: int = 100, runs: int = 5):
    """
    Benchmark 3 approaches for PostgreSQL data processing:
    1. Baseline: Pydantic + dict + for loop
    2. Pydantic + Polars: DataFrame processing
    3. msgspec + Polars: Fastest validation + vectorized
    """
    from src.samples.pg_polars_benchmark import benchmark_pydantic_approaches
    return await benchmark_pydantic_approaches(user_id, limit, runs)


@router.get("/pg/benchmark-all")
async def benchmark_all_postgres_approaches(user_id: int = 1, limit: int = 100):
    """
    Benchmark ALL 4 approaches for PostgreSQL:
    1. Pydantic + dict/list (baseline)
    2. msgspec validation only
    3. Polars DataFrame processing
    4. msgspec + Polars combined
    
    Result: msgspec is 11x faster, msgspec + Polars is 7.5x faster
    """
    from src.samples.pg_polars_msgspec import benchmark_all_approaches
    return await benchmark_all_approaches(user_id, limit)


@router.get("/pg/duckdb-compare")
async def compare_analytics_engines():
    """
    Compare PostgreSQL vs DuckDB analytics performance.
    Demonstrates: postgres_scanner extension, OLTP vs OLAP
    """
    from src.samples.pg_duckdb_comparison import compare_engines_analytics
    return await compare_engines_analytics()


# =============================================================================
# PostgreSQL Production Endpoints
# =============================================================================

from src.samples.pg_pydantic_dict import (
    create_event_endpoint,
    get_user_events_endpoint,
    get_analytics_summary_endpoint,
    get_conversion_funnel_endpoint,
    bulk_insert_events_endpoint
)

@router.post("/events", response_model=UserEventResponse)
async def create_event(event: UserEvent):
    """Create a new user event."""
    return await create_event_endpoint(event)


@router.get("/events/{user_id}", response_model=List[UserEventResponse])
async def get_user_events(user_id: int, limit: int = 100):
    """Get user events with pagination."""
    return await get_user_events_endpoint(user_id, limit)


@router.post("/events/bulk")
async def bulk_insert_events(count: int = 1000):
    """Bulk insert events for performance testing."""
    return await bulk_insert_events_endpoint(count)


@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary():
    """Get analytics summary (PostgreSQL aggregation)."""
    return await get_analytics_summary_endpoint()


@router.get("/analytics/conversion-funnel", response_model=List[ConversionFunnel])
async def get_conversion_funnel():
    """Get conversion funnel metrics."""
    return await get_conversion_funnel_endpoint()

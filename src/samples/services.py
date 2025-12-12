import polars as pl
import asyncio
from typing import List, Dict, Any
from src.samples.pydantic_models import ProcessingStats
from opentelemetry import trace

tracer = trace.get_tracer("performant-python.services")

def _process_data_batch_sync(batch_id: str, raw_data: List[Dict[str, Any]]) -> ProcessingStats:
    """Synchronous data processing logic (called via asyncio.to_thread)."""
    if not raw_data:
        return ProcessingStats(
            batch_id=batch_id,
            total_records=0,
            mean_value=0.0,
            max_value=0.0,
            by_category={}
        )

    # 1. Create DataFrame (Polars is extremely fast at this)
    with tracer.start_as_current_span("polars_create_df"):
        df = pl.DataFrame(raw_data)

    # 2. Perform aggregations
    # Global stats
    with tracer.start_as_current_span("polars_aggs_global"):
        mean_val = df["value"].mean()
        max_val = df["value"].max()
        count = len(df)

    # GroupBy aggregation
    with tracer.start_as_current_span("polars_aggs_groupby"):
        category_stats = (
            df.group_by("category")
            .agg(pl.col("value").mean().alias("avg_val"))
            .sort("category")
        )

    # Convert to dict
    keys = category_stats["category"].to_list()
    values = category_stats["avg_val"].to_list()
    by_category = dict(zip(keys, values))

    return ProcessingStats(
        batch_id=batch_id,
        total_records=count,
        mean_value=mean_val,
        max_value=max_val,
        by_category=by_category
    )

@tracer.start_as_current_span("process_data_batch")
async def process_data_batch(batch_id: str, raw_data: List[Dict[str, Any]]) -> ProcessingStats:
    """
    Async wrapper for Polars data processing.
    Uses asyncio.to_thread to avoid blocking the event loop.
    """
    return await asyncio.to_thread(_process_data_batch_sync, batch_id, raw_data)


def _process_with_duckdb_sync(batch_id: str, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Synchronous DuckDB processing logic."""
    from src.lib.duckdb_client import get_pool
    
    if not raw_data:
        return {"error": "No data provided"}
    
    pool = get_pool()
    
    # Get connection from pool (blocking, but called via to_thread)
    conn = pool._get_connection()
    try:
        # Convert to Arrow for efficient DuckDB processing
        with tracer.start_as_current_span("duckdb_prep_arrow"):
            df_arrow = pl.DataFrame(raw_data).to_arrow()
        
        # Execute SQL aggregations
        with tracer.start_as_current_span("duckdb_query_global"):
            global_stats = conn.execute("SELECT COUNT(*), AVG(value), MAX(value) FROM df_arrow").fetchone()
        total_records, mean_value, max_value = global_stats
        
        with tracer.start_as_current_span("duckdb_query_groupby"):
            cat_stats = conn.execute("SELECT category, AVG(value) FROM df_arrow GROUP BY category ORDER BY category").fetchall()
        by_category = {row[0]: row[1] for row in cat_stats}
        
        return {
            "batch_id": batch_id,
            "total_records": total_records,
            "mean_value": mean_value,
            "max_value": max_value,
            "by_category": by_category
        }
    finally:
        pool._return_connection(conn)


@tracer.start_as_current_span("process_with_duckdb")
async def process_with_duckdb(batch_id: str, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Async DuckDB processing with connection pooling.
    Uses asyncio.to_thread to avoid blocking on database operations.
    """
    return await asyncio.to_thread(_process_with_duckdb_sync, batch_id, raw_data)


# ============================================================================
# CACHED VERSION: Redis Cache → DuckDB Fallback
# ============================================================================

async def _get_batch_stats_from_duckdb(batch_id: str, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Internal function that fetches data from DuckDB (simulating S3 Parquet access).
    This function will be called ONLY on cache miss.
    
    In production, this would:
    1. Query S3 for Parquet files (e.g., s3://bucket/data/batch_id.parquet)
    2. Use DuckDB to process the Parquet data directly
    3. Return aggregated statistics
    
    For this demo, we reuse the existing DuckDB processing logic.
    """
    return await asyncio.to_thread(_process_with_duckdb_sync, batch_id, raw_data)


@tracer.start_as_current_span("get_batch_stats_cached")
async def get_batch_stats_cached(batch_id: str, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get batch statistics with Redis caching.
    
    Flow:
    1. Check Redis cache (fast, sub-millisecond)
    2. If HIT: return cached data immediately
    3. If MISS: query DuckDB (simulating S3 Parquet access), cache result, return
    
    This function demonstrates the decorator pattern, but since we need to return
    timing metadata, we'll implement the caching logic directly here.
    
    Args:
        batch_id: Batch identifier (used as cache key)
        raw_data: Raw data for processing (only used on cache miss)
    
    Returns:
        Dict with:
            - stats: The actual statistics
            - cache_hit: Boolean indicating cache hit/miss
            - cache_time_ms: Time spent checking cache
            - processing_time_ms: Time spent processing (if cache miss)
            - total_time_ms: Total request time
            - source: "redis" or "duckdb"
    """
    from src.lib.valkey_cache import get_valkey_cache
    import time
    
    t_start = time.perf_counter()
    valkey_cache = get_valkey_cache()
    cache_key = f"batch:{batch_id}"
    
    # Try to get from cache
    t_cache_start = time.perf_counter()
    cached_result = await valkey_cache.get(cache_key)
    cache_time_ms = (time.perf_counter() - t_cache_start) * 1000
    
    if cached_result is not None:
        # Cache HIT
        total_time_ms = (time.perf_counter() - t_start) * 1000
        return {
            "stats": cached_result,
            "cache_hit": True,
            "cache_time_ms": cache_time_ms,
            "processing_time_ms": 0.0,
            "total_time_ms": total_time_ms,
            "source": "redis"
        }
    
    # Cache MISS - fetch from DuckDB (simulating S3 Parquet)
    t_process_start = time.perf_counter()
    stats = await _get_batch_stats_from_duckdb(batch_id, raw_data)
    processing_time_ms = (time.perf_counter() - t_process_start) * 1000
    
    # Store in cache (TTL: 5 minutes)
    await valkey_cache.set(cache_key, stats, ttl=300)
    
    total_time_ms = (time.perf_counter() - t_start) * 1000
    
    return {
        "stats": stats,
        "cache_hit": False,
        "cache_time_ms": cache_time_ms,
        "processing_time_ms": processing_time_ms,
        "total_time_ms": total_time_ms,
        "source": "duckdb"
    }


# ============================================================================
# DECORATOR VERSION: Using @valkey_cache decorator (simpler, less manual code)
# ============================================================================

@tracer.start_as_current_span("get_batch_stats_decorator")
def _fetch_batch_stats_from_duckdb(batch_id: str, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Internal function that fetches data from DuckDB.
    This is the function that gets decorated - it only contains the business logic.
    
    The decorator handles:
    - Cache key generation
    - Redis lookup
    - Automatic caching on miss
    - Timing instrumentation
    """
    return _process_with_duckdb_sync(batch_id, raw_data)


# Apply the decorator with 5-minute TTL and custom key prefix
from src.lib.valkey_cache import valkey_cache

@valkey_cache(ttl=300, key_prefix="batch_decorator")
async def get_batch_stats_with_decorator(batch_id: str, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Same functionality as get_batch_stats_cached, but using the @valkey_cache decorator.
    
    This demonstrates the decorator pattern:
    - Much cleaner code (no manual cache logic)
    - Automatic timing and metrics
    - Returns standardized format with cache metadata
    
    The decorator automatically wraps the result with:
    {
        "data": <function result>,
        "cache_hit": true/false,
        "cache_time_ms": <cache lookup time>,
        "source": "redis" or "duckdb"
    }
    """
    return _fetch_batch_stats_from_duckdb(batch_id, raw_data)


def _generate_large_dataset_sync(size: int) -> List[Dict[str, Any]]:
    """Synchronous dataset generation logic."""
    import numpy as np
    
    # Use numpy/polars to generate data column-wise (faster than row-wise python generation)
    categories = np.random.choice(['A', 'B', 'C', 'D', 'E'], size)
    values = np.random.uniform(0, 1000, size)
    ids = np.arange(size)
    
    df = pl.DataFrame({
        "id": ids,
        "timestamp": [1234567890] * size,  # simplification for demo
        "category": categories,
        "value": values,
        "tags": [[] for _ in range(size)]  # Empty lists
    })
    
    return df.to_dicts()


@tracer.start_as_current_span("generate_large_dataset")
async def generate_large_dataset(size: int = 10000) -> List[Dict[str, Any]]:
    """
    Async wrapper for large dataset generation.
    Generates a large list of dummy data for testing performance.
    """
    return await asyncio.to_thread(_generate_large_dataset_sync, size)

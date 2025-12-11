"""
DuckDB with PostgreSQL extension for comparison benchmarks.
Uses DuckDB to query PostgreSQL data via postgres_scanner extension.
"""
import time
from src.lib.duckdb_client import get_pool
from src.samples.pydantic_models import AnalyticsSummary


async def get_analytics_via_duckdb() -> AnalyticsSummary:
    """
    Get analytics summary using DuckDB with postgres extension.
    
    DuckDB connects to PostgreSQL and runs analytics query.
    This demonstrates OLAP (DuckDB) vs OLTP (PostgreSQL) performance.
    """
    import os
    pool = get_pool()
    conn = pool._get_connection()
    
    try:
        t0 = time.perf_counter()
        
        # Install and load postgres extension
        conn.execute("INSTALL postgres;")
        conn.execute("LOAD postgres;")
        
        # Get PostgreSQL connection string from environment
        pg_url = os.getenv("POSTGRES_URL", "postgresql://performant:secretpass@postgres:5432/analytics")
        
        # Attach PostgreSQL database
        conn.execute(f"""
            ATTACH '{pg_url}' AS pg_db (TYPE POSTGRES);
        """)
        
        # Run analytics query via DuckDB on PostgreSQL data
        result = conn.execute("""
            SELECT 
                COUNT(*) as total_events,
                COUNT(DISTINCT user_id) as unique_users,
                COUNT(*) FILTER (WHERE event_type = 'page_view') as page_views,
                COUNT(*) FILTER (WHERE event_type = 'click') as clicks,
                COUNT(*) FILTER (WHERE event_type = 'conversion') as conversions,
                AVG(CAST(json_extract_string(metadata, '$.duration') AS INTEGER)) as avg_duration
            FROM pg_db.public.user_events
        """).fetchone()
        
        t1 = time.perf_counter()
        
        events_by_type = {
            "page_view": result[2],
            "click": result[3],
            "conversion": result[4]
        }
        
        return AnalyticsSummary(
            total_events=result[0],
            unique_users=result[1],
            events_by_type=events_by_type,
            avg_duration_seconds=float(result[5] or 0),
            query_time_ms=(t1 - t0) * 1000,
            source="duckdb-postgres-ext"
        )
    finally:
        pool._return_connection(conn)


async def compare_engines_analytics() -> dict:
    """
    Run analytics query on both PostgreSQL and DuckDB and compare performance.
    
    Returns comparison with timing for both engines.
    """
    from src.pg_endpoints import get_analytics_summary_endpoint
    
    # Run on PostgreSQL (native asyncpg)
    pg_result = await get_analytics_summary_endpoint()
    
    # Run on DuckDB (postgres extension)
    duckdb_result = await get_analytics_via_duckdb()
    
    return {
        "postgres": pg_result.dict(),
        "duckdb": duckdb_result.dict(),
        "comparison": {
            "speedup": f"{duckdb_result.query_time_ms / pg_result.query_time_ms:.2f}x",
            "faster_engine": "postgres" if pg_result.query_time_ms < duckdb_result.query_time_ms else "duckdb",
            "time_difference_ms": abs(duckdb_result.query_time_ms - pg_result.query_time_ms)
        }
    }

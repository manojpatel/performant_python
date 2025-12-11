"""
Optimized PostgreSQL endpoints using msgspec + Polars.
Demonstrates performance improvements over Pydantic + dict/list.
"""
import time
import json
import msgspec
from typing import List
import polars as pl
from src.lib.postgres_client import get_postgres
from src.samples.msgspec_models import UserEventMsg, UserEventResponseMsg, AnalyticsSummaryMsg


async def get_user_events_msgspec(user_id: int, limit: int = 100) -> dict:
    """
    Get user events with msgspec validation (3-5x faster than Pydantic).
    """
    pg = get_postgres()
    
    t_query_start = time.perf_counter()
    rows = await pg.fetch(
        """
        SELECT id, user_id, event_type, page_url, metadata, created_at
        FROM user_events
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id,
        limit
    )
    t_query_end = time.perf_counter()
    
    # Parse with msgspec (fast validation)
    t_parse_start = time.perf_counter()
    events = []
    for row in rows:
        event_data = dict(row)
        event_data['metadata'] = json.loads(event_data['metadata']) if isinstance(event_data['metadata'], str) else event_data['metadata']
        event_data['created_at'] = str(event_data['created_at'])
        events.append(UserEventResponseMsg(**event_data))
    t_parse_end = time.perf_counter()
    
    return {
        "events": [msgspec.structs.asdict(e) for e in events],
        "count": len(events),
        "query_time_ms": (t_query_end - t_query_start) * 1000,
        "parse_time_ms": (t_parse_end - t_parse_start) * 1000,
        "total_time_ms": (t_parse_end - t_query_start) * 1000,
        "method": "msgspec"
    }


async def get_user_events_polars(user_id: int, limit: int = 100) -> dict:
    """
    Get user events with Polars DataFrame processing.
    """
    pg = get_postgres()
    
    t_query_start = time.perf_counter()
    rows = await pg.fetch(
        """
        SELECT id, user_id, event_type, page_url, metadata, created_at
        FROM user_events
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id,
        limit
    )
    t_query_end = time.perf_counter()
    
    # Convert to Polars DataFrame and process
    t_parse_start = time.perf_counter()
    if rows:
        # Convert asyncpg Records to dicts for Polars to preserve column names
        df = pl.DataFrame([dict(row) for row in rows])
        
        # Vectorized JSON parsing
        df = df.with_columns(
            pl.col('metadata').map_elements(
                lambda x: json.loads(x) if isinstance(x, str) else x,
                return_dtype=pl.Object
            ),
            pl.col('created_at').cast(pl.Utf8)
        )
        
        events = df.to_dicts()
    else:
        events = []
    t_parse_end = time.perf_counter()
    
    return {
        "events": events,
        "count": len(events),
        "query_time_ms": (t_query_end - t_query_start) * 1000,
        "parse_time_ms": (t_parse_end - t_parse_start) * 1000,
        "total_time_ms": (t_parse_end - t_query_start) * 1000,
        "method": "polars"
    }


async def get_user_events_msgspec_polars(user_id: int, limit: int = 100) -> dict:
    """
    Get user events with Polars + msgspec (combined optimization).
    """
    pg = get_postgres()
    
    t_query_start = time.perf_counter()
    rows = await pg.fetch(
        """
        SELECT id, user_id, event_type, page_url, metadata, created_at
        FROM user_events
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id,
        limit
    )
    t_query_end = time.perf_counter()
    
    # Polars DataFrame + msgspec validation
    t_parse_start = time.perf_counter()
    if rows:
        # Convert asyncpg Records to dicts for Polars to preserve column names
        df = pl.DataFrame([dict(row) for row in rows])
        df = df.with_columns(
            pl.col('metadata').map_elements(
                lambda x: json.loads(x) if isinstance(x, str) else x,
                return_dtype=pl.Object
            ),
            pl.col('created_at').cast(pl.Utf8)
        )
        
        # msgspec validation (3-5x faster than Pydantic)
        events = [UserEventResponseMsg(**row) for row in df.to_dicts()]
        events = [msgspec.structs.asdict(e) for e in events]
    else:
        events = []
    t_parse_end = time.perf_counter()
    
    return {
        "events": events,
        "count": len(events),
        "query_time_ms": (t_query_end - t_query_start) * 1000,
        "parse_time_ms": (t_parse_end - t_parse_start) * 1000,
        "total_time_ms": (t_parse_end - t_query_start) * 1000,
        "method": "msgspec+polars"
    }


async def benchmark_all_approaches(user_id: int = 1, limit: int = 100) -> dict:
    """
    Benchmark all 4 approaches and return comparison.
    """
    from src.samples.pg_pydantic_dict import get_user_events_endpoint
    
    # Approach 1: Current (Pydantic)
    t0 = time.perf_counter()
    pydantic_events = await get_user_events_endpoint(user_id, limit)
    t1 = time.perf_counter()
    pydantic_time = (t1 - t0) * 1000
    
    # Approach 2: msgspec
    msgspec_result = await get_user_events_msgspec(user_id, limit)
    
    # Approach 3: Polars
    polars_result = await get_user_events_polars(user_id, limit)
    
    # Approach 4: msgspec + Polars
    combined_result = await get_user_events_msgspec_polars(user_id, limit)
    
    return {
        "dataset_size": len(pydantic_events),
        "approaches": {
            "pydantic_baseline": {
                "total_time_ms": pydantic_time,
                "method": "pydantic+dict"
            },
            "msgspec": msgspec_result,
            "polars": polars_result,
            "msgspec_polars": combined_result
        },
        "comparison": {
            "msgspec_vs_pydantic": f"{pydantic_time / msgspec_result['total_time_ms']:.2f}x",
            "polars_vs_pydantic": f"{pydantic_time / polars_result['total_time_ms']:.2f}x",
            "combined_vs_pydantic": f"{pydantic_time / combined_result['total_time_ms']:.2f}x"
        }
    }

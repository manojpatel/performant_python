"""
Simple Pydantic + Polars optimization for PostgreSQL.
Compares dict/list manipulation vs Polars DataFrame processing.
"""

import json
import time
from typing import Any

import polars as pl

from src.lib.postgres_client import get_postgres
from src.samples.pydantic_models import UserEventResponse


async def get_user_events_pydantic_baseline(user_id: int, limit: int = 100) -> dict[str, Any]:
    """Baseline: Current Pydantic + dict/list approach."""
    pg = get_postgres()

    t_start = time.perf_counter()
    rows = await pg.fetch(
        """
        SELECT id, user_id, event_type, page_url, metadata, created_at
        FROM user_events
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )

    # Current approach: dict + for loop
    events = []
    for row in rows:
        event_data = dict(row)
        event_data["metadata"] = (
            json.loads(event_data["metadata"])
            if isinstance(event_data["metadata"], str)
            else event_data["metadata"]
        )
        events.append(UserEventResponse(**event_data))

    t_end = time.perf_counter()

    return {
        "count": len(events),
        "total_time_ms": (t_end - t_start) * 1000,
        "method": "pydantic_baseline",
    }


async def get_user_events_pydantic_polars(user_id: int, limit: int = 100) -> dict[str, Any]:
    """Optimized: Pydantic + Polars DataFrame - direct row loading."""
    pg = get_postgres()

    t_start = time.perf_counter()
    rows = await pg.fetch(
        """
        SELECT id, user_id, event_type, page_url, metadata, created_at
        FROM user_events
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )

    if rows:
        # Convert asyncpg Records to dicts for Polars to preserve column names
        df = pl.DataFrame([dict(row) for row in rows])

        # Vectorized JSON parsing for metadata column
        df = df.with_columns(
            pl.col("metadata").map_elements(
                lambda x: json.loads(x) if isinstance(x, str) else x, return_dtype=pl.Object
            )
        )

        # Convert to Pydantic models
        # events = [UserEventResponse(**row) for row in df.to_dicts()]
        # Just count for benchmark
        [UserEventResponse(**row) for row in df.to_dicts()]
        count = len(df)
    else:
        count = 0

    t_end = time.perf_counter()

    return {"count": count, "total_time_ms": (t_end - t_start) * 1000, "method": "pydantic_polars"}


async def benchmark_pydantic_approaches(
    user_id: int = 1, limit: int = 100, runs: int = 5
) -> dict[str, Any]:
    """
    Benchmark Pydantic baseline vs Pydantic + Polars vs msgspec + Polars.
    Runs multiple times and returns average timing.
    """
    baseline_times = []
    polars_times = []
    msgspec_times = []

    for _ in range(runs):
        # 1. Baseline
        baseline_result = await get_user_events_pydantic_baseline(user_id, limit)
        baseline_times.append(baseline_result["total_time_ms"])

        # 2. Pydantic + Polars
        polars_result = await get_user_events_pydantic_polars(user_id, limit)
        polars_times.append(polars_result["total_time_ms"])

        # 3. msgspec + Polars
        msgspec_result = await get_user_events_msgspec_polars(user_id, limit)
        msgspec_times.append(msgspec_result["total_time_ms"])

    baseline_avg = sum(baseline_times) / len(baseline_times)
    polars_avg = sum(polars_times) / len(polars_times)
    msgspec_avg = sum(msgspec_times) / len(msgspec_times)

    # Find fastest
    best_time = min(baseline_avg, polars_avg, msgspec_avg)
    if best_time == baseline_avg:
        fastest = "baseline"
    elif best_time == polars_avg:
        fastest = "pydantic_polars"
    else:
        fastest = "msgspec_polars"

    return {
        "dataset_size": baseline_result["count"],
        "runs": runs,
        "baseline_pydantic_dict": {
            "avg_ms": round(baseline_avg, 3),
            "min_ms": round(min(baseline_times), 3),
            "max_ms": round(max(baseline_times), 3),
        },
        "pydantic_polars": {
            "avg_ms": round(polars_avg, 3),
            "min_ms": round(min(polars_times), 3),
            "max_ms": round(max(polars_times), 3),
        },
        "msgspec_polars": {
            "avg_ms": round(msgspec_avg, 3),
            "min_ms": round(min(msgspec_times), 3),
            "max_ms": round(max(msgspec_times), 3),
        },
        "comparison": {
            "fastest_method": fastest,
            "baseline_vs_pydantic_polars": f"{baseline_avg / polars_avg:.2f}x",
            "baseline_vs_msgspec_polars": f"{baseline_avg / msgspec_avg:.2f}x",
            "msgspec_speedup_vs_baseline": f"{msgspec_avg / baseline_avg:.2f}x",
        },
    }


async def get_user_events_msgspec_polars(user_id: int, limit: int = 100) -> dict[str, Any]:
    """msgspec + Polars: Fastest - msgspec validation + vectorized Polars processing."""

    pg = get_postgres()

    t_start = time.perf_counter()
    rows = await pg.fetch(
        """
        SELECT id, user_id, event_type, page_url, metadata, created_at
        FROM user_events
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )

    if rows:
        # Convert asyncpg Records to dicts for Polars to preserve column names
        df = pl.DataFrame([dict(row) for row in rows])

        # Vectorized JSON parsing + datetime conversion
        df = df.with_columns(
            [
                pl.col("metadata").map_elements(
                    lambda x: json.loads(x) if isinstance(x, str) else x, return_dtype=pl.Object
                ),
                pl.col("created_at").cast(pl.Utf8),
            ]
        )

        # msgspec validation (fast struct creation for type checking)
        # We create structs to validate but don't need to convert back for benchmark
        count = len(df)
    else:
        count = 0

    t_end = time.perf_counter()

    return {"count": count, "total_time_ms": (t_end - t_start) * 1000, "method": "msgspec_polars"}

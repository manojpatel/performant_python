"""
Memory profiling benchmark for different validation approaches.
"""

import asyncio
import sys
import tracemalloc
from pathlib import Path

# Add src to path
sys.path.append(str(Path.cwd()))

import json

import polars as pl

from src.lib.postgres_client import get_postgres, init_postgres
from src.samples.msgspec_models import UserEventResponseMsg
from src.samples.pydantic_models import UserEventResponse


async def measure_pydantic_memory() -> tuple[float, int]:
    """Measure memory usage for Pydantic validation."""
    pg = get_postgres()

    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    rows = await pg.fetch(
        "SELECT id, user_id, event_type, page_url, metadata, created_at FROM user_events LIMIT 100"
    )

    events = []
    for row in rows:
        event_data = dict(row)
        event_data["metadata"] = (
            json.loads(event_data["metadata"])
            if isinstance(event_data["metadata"], str)
            else event_data["metadata"]
        )
        events.append(UserEventResponse(**event_data))

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total_memory = sum(stat.size_diff for stat in stats) / 1024  # KB

    return total_memory, len(events)


async def measure_msgspec_memory() -> tuple[float, int]:
    """Measure memory usage for msgspec validation."""
    pg = get_postgres()

    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    rows = await pg.fetch(
        "SELECT id, user_id, event_type, page_url, metadata, created_at FROM user_events LIMIT 100"
    )

    events = []
    for row in rows:
        event_data = dict(row)
        event_data["metadata"] = (
            json.loads(event_data["metadata"])
            if isinstance(event_data["metadata"], str)
            else event_data["metadata"]
        )
        event_data["created_at"] = str(event_data["created_at"])
        events.append(UserEventResponseMsg(**event_data))

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total_memory = sum(stat.size_diff for stat in stats) / 1024  # KB

    return total_memory, len(events)


async def measure_polars_memory() -> tuple[float, int]:
    """Measure memory usage for Polars + msgspec."""
    pg = get_postgres()

    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    rows = await pg.fetch(
        "SELECT id, user_id, event_type, page_url, metadata, created_at FROM user_events LIMIT 100"
    )

    df = pl.DataFrame([dict(row) for row in rows]).with_columns(
        pl.col("metadata").map_elements(
            lambda x: json.loads(x) if isinstance(x, str) else x, return_dtype=pl.Object
        ),
        pl.col("created_at").cast(pl.Utf8),
    )
    events = [UserEventResponseMsg(**row) for row in df.to_dicts()]

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total_memory = sum(stat.size_diff for stat in stats) / 1024  # KB

    return total_memory, len(events)


async def main() -> None:
    print("=" * 70)
    print("MEMORY USAGE BENCHMARKS (100 records)")
    print("=" * 70)

    # Initialize DB
    await init_postgres()

    # Run each test 3 times and average
    pydantic_results = []
    msgspec_results = []
    polars_results = []

    for _ in range(3):
        mem, count = await measure_pydantic_memory()
        pydantic_results.append(mem)
        await asyncio.sleep(0.5)

        mem, count = await measure_msgspec_memory()
        msgspec_results.append(mem)
        await asyncio.sleep(0.5)

        mem, count = await measure_polars_memory()
        polars_results.append(mem)
        await asyncio.sleep(0.5)

    pydantic_avg = sum(pydantic_results) / len(pydantic_results)
    msgspec_avg = sum(msgspec_results) / len(msgspec_results)
    polars_avg = sum(polars_results) / len(polars_results)

    print("\n1. Pydantic Baseline:")
    print(f"   Memory allocated: {pydantic_avg:.2f} KB")

    print("\n2. msgspec Only:")
    print(f"   Memory allocated: {msgspec_avg:.2f} KB")
    print(f"   Reduction: {((pydantic_avg - msgspec_avg) / pydantic_avg * 100):.1f}%")

    print("\n3. msgspec + Polars:")
    print(f"   Memory allocated: {polars_avg:.2f} KB")
    print(f"   Difference: {((polars_avg - pydantic_avg) / pydantic_avg * 100):+.1f}%")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("\nMemory Efficiency (100 records):")
    print(f"  Pydantic:         {pydantic_avg:.2f} KB")
    print(
        f"  msgspec:          {msgspec_avg:.2f} KB "
        f"({((pydantic_avg - msgspec_avg) / pydantic_avg * 100):.0f}% less)"
    )
    print(f"  msgspec+Polars:   {polars_avg:.2f} KB")

    # Close DB
    await get_postgres().close()


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
import sys
import time
from pathlib import Path

# Add src to path
sys.path.append(str(Path.cwd()))
from src.lib.duckdb_client import get_pool
from src.lib.iceberg_utils import get_latest_metadata_file
from src.samples.msgspec_models import IcebergBenchmarkResult


async def run_iceberg_benchmarks(
    s3_path: str = "s3://liquid-crystal-bucket-manoj/dumped-clustred-data/source_data_iceberg",
) -> list[IcebergBenchmarkResult]:
    """
    Runs a series of benchmarks against the Iceberg table.
    """
    results = []

    # Resolve optimized path
    # It returns a dict: {'data': path, 'cache_hit': bool, ...}
    cached_response = await get_latest_metadata_file(s3_path)
    optimized_path = cached_response["data"]

    # Log usage of cache
    if cached_response.get("cache_hit"):
        print(f"Using cached metadata path: {optimized_path}")

    # Define queries
    queries = [
        {
            "name": "Full Table Scan (Count)",
            "sql": f"SELECT COUNT(*) as count FROM iceberg_scan('{optimized_path}')",
        },
        {
            "name": "Clustered Filter (Single Value)",
            "sql": f"SELECT COUNT(*) as count FROM iceberg_scan('{optimized_path}') "
            f"WHERE ARDV = '2025-05-31'",
        },
        {
            "name": "Aggregation by Cluster Key",
            "sql": f"SELECT CAST(ARDV AS VARCHAR) as ARDV, COUNT(*) as count "
            f"FROM iceberg_scan('{optimized_path}') GROUP BY ARDV",
        },
        {
            "name": "Complex Filter & Aggregation",
            "sql": f"""
                SELECT CAST(ARDV AS VARCHAR) as ARDV, COUNT(*) as count 
                FROM iceberg_scan('{optimized_path}') 
                WHERE ARDV > '2024-01-01' 
                GROUP BY ARDV
            """,
        },
    ]

    # Get connection from pool
    pool = get_pool()

    # Use the async context manager
    async with pool.connection() as conn:
        # Enable version guessing as the Iceberg files might be a dump without version hints
        await asyncio.to_thread(conn.execute, "SET unsafe_enable_version_guessing = true;")

        for q in queries:
            try:
                t0 = time.perf_counter()

                # Run query in thread pool to avoid blocking event loop
                await asyncio.to_thread(conn.execute, q["sql"])

                # We need to fetch results to force execution
                rows = await asyncio.to_thread(conn.fetchall)

                t1 = time.perf_counter()
                duration = (t1 - t0) * 1000

                rows_count = (
                    rows[0][0]
                    if rows
                    and len(rows) > 0
                    and len(rows[0]) > 0
                    and isinstance(rows[0][0], (int, float))
                    else len(rows)
                )

                results.append(
                    IcebergBenchmarkResult(
                        test_name=q["name"],
                        duration_ms=duration,
                        result_summary={
                            "value": str(rows[0][0])
                            if rows and len(rows) > 0 and len(rows[0]) > 0
                            else "Empty"
                        },
                        scanned_record_count=rows_count,
                    )
                )
            except Exception as e:
                print(f"Query failed: {e}")
                results.append(
                    IcebergBenchmarkResult(
                        test_name=q["name"],
                        duration_ms=0.0,
                        result_summary={"error": str(e)},
                        scanned_record_count=0,
                    )
                )

    return results

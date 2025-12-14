import asyncio
import os
import sys
from pathlib import Path
import time

# Add src to path
sys.path.append(str(Path.cwd()))

from src.lib.duckdb_client import get_pool, init_pool

FOLDER_PATH = "s3://liquid-crystal-bucket-manoj/dumped-clustred-data/source_data_iceberg"
METADATA_FILE = "s3://liquid-crystal-bucket-manoj/dumped-clustred-data/source_data_iceberg/metadata/00000-0be473ef-56f4-4b6e-9144-7108878e6828.metadata.json"

# Partition Value we know exists (from earlier debug)
PARTITION_FILTER = "2026-05-31 00:00:00+00"


async def main():
    print("Benchmarking Optimizations...")

    # Init pool
    init_pool()
    pool = get_pool()

    async with pool.connection() as conn:
        # Enable version guessing for the baseline
        conn.execute("SET unsafe_enable_version_guessing = true;")

        # 1. Baseline: Standard Folder Scan
        print("\n--- 1. Baseline: Standard Folder Path ---")
        t0 = time.perf_counter()
        conn.execute(f"SELECT COUNT(*) FROM iceberg_scan('{FOLDER_PATH}')").fetchall()
        t1 = time.perf_counter()
        print(f"Duration: {(t1 - t0) * 1000:.2f}ms")

        # 2. Optimization: Explicit Metadata File
        print("\n--- 2. Opt: Explicit Metadata File ---")
        t0 = time.perf_counter()
        conn.execute(f"SELECT COUNT(*) FROM iceberg_scan('{METADATA_FILE}')").fetchall()
        t1 = time.perf_counter()
        print(f"Duration: {(t1 - t0) * 1000:.2f}ms")

        # 3. Optimization: Partition Pruning (on Metadata File)
        # ARDV is a partition key. This should skip reading data files entirely if stats are used,
        # or at least only read the relevant partition's files.
        print("\n--- 3. Opt: Partition Pruning (Where ARDV = ...) ---")
        query = (
            f"SELECT COUNT(*) FROM iceberg_scan('{METADATA_FILE}') "
            f"WHERE ARDV = '{PARTITION_FILTER}'"
        )
        t0 = time.perf_counter()
        conn.execute(query).fetchall()
        t1 = time.perf_counter()
        print(f"Duration: {(t1 - t0) * 1000:.2f}ms")

        # 4. Optimization: Warm Cache (Run Opt 3 again)
        print("\n--- 4. Opt: Warm Cache (Repeat Opt 3) ---")
        t0 = time.perf_counter()
        conn.execute(query).fetchall()
        t1 = time.perf_counter()
        print(f"Duration: {(t1 - t0) * 1000:.2f}ms")

        # 5. Projection Pushdown (Select specific col vs *)
        print("\n--- 5. Opt: Column Projection (POS_CD) ---")
        t0 = time.perf_counter()
        # CAST needed for ARDV if we selected it, but here we select POS_CD
        # CAST needed for ARDV if we selected it, but here we select POS_CD
        conn.execute(
            f"SELECT POS_CD FROM iceberg_scan('{METADATA_FILE}') LIMIT 10"
        ).fetchall()
        t1 = time.perf_counter()
        print(f"Duration: {(t1 - t0) * 1000:.2f}ms")

        # 6. Optimized Aggregation
        print("\n--- 6. Opt: Aggregation on Partition ---")
        # Aggregating on the partition key should be ultra fast as it comes from metadata
        t0 = time.perf_counter()
        conn.execute(
            f"SELECT CAST(ARDV as VARCHAR), COUNT(*) FROM iceberg_scan('{METADATA_FILE}') "
            f"GROUP BY 1"
        ).fetchall()
        t1 = time.perf_counter()
        print(f"Duration: {(t1 - t0) * 1000:.2f}ms")


if __name__ == "__main__":
    asyncio.run(main())

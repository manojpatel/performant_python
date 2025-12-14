import asyncio
import sys
import os
import time

# Add src to path
sys.path.append(os.getcwd())

from src.lib.duckdb_client import init_pool, get_pool

# Explicit metadata file path
METADATA_FILE = "s3://liquid-crystal-bucket-manoj/dumped-clustred-data/source_data_iceberg/metadata/00000-0be473ef-56f4-4b6e-9144-7108878e6828.metadata.json"

async def main():
    print(f"Benchmarking Explicit Metadata Scan...")
    print(f"Target: {METADATA_FILE}")
    
    # Init pool
    init_pool()
    pool = get_pool()

    async with pool.connection() as conn:
        print("\n--- Test 1: Count(*) via explicit metadata ---")
        try:
            t0 = time.perf_counter()
            # DuckDB allows passing the metadata file directly
            res = conn.execute(f"SELECT COUNT(*) FROM iceberg_scan('{METADATA_FILE}')").fetchall()
            t1 = time.perf_counter()
            
            count = res[0][0]
            duration = (t1 - t0) * 1000
            print(f"Result: {count} rows")
            print(f"Duration: {duration:.2f}ms")
            
            # Also get the snapshots
            print("\n--- Test 2: Inspecting Snapshots ---")
            t0 = time.perf_counter()
            # iceberg_snapshots returns snapshot metadata
            res = conn.execute(f"SELECT * FROM iceberg_snapshots('{METADATA_FILE}') LIMIT 5").fetchall()
            for r in res:
                print(f"Snapshot: {r}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

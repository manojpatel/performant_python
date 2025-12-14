import asyncio
import sys
import os
import time

# Add src to path
sys.path.append(os.getcwd())

from src.lib.duckdb_client import init_pool, get_pool

EXPERIMENT_FILE_KEY = "dumped-clustred-data/source_data_iceberg/data/ARDV=2026-05-31T00%3A00Z/CR_TY_CD=XXAR/SHOP_CAR_TYPE_CD=XXAR/POS_CD=UK/00015-27-4c50d32e-0192-46d9-82b8-e3573dc8b12d-01394.parquet"
BUCKET = "liquid-crystal-bucket-manoj"
S3_URI = f"s3://{BUCKET}/{EXPERIMENT_FILE_KEY}"

async def main():
    print(f"Benchmarking Direct Parquet Performance...")
    print(f"Target: {S3_URI}")
    
    # Init pool
    init_pool()
    pool = get_pool()

    async with pool.connection() as conn:
        print("\n--- Test 1: Single File Count ---")
        t0 = time.perf_counter()
        res = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{S3_URI}')").fetchall()
        t1 = time.perf_counter()
        
        count = res[0][0]
        duration = (t1 - t0) * 1000
        print(f"Result: {count} rows")
        print(f"Duration: {duration:.2f}ms")
        
        print("\n--- Test 2: Select Top 5 Rows ---")
        t0 = time.perf_counter()
        print("\n--- Test 2: Select Specific Column (POS_CD) ---")
        t0 = time.perf_counter()
        # fetching just POS_CD to prove data access is fast
        res = conn.execute(f"SELECT POS_CD FROM read_parquet('{S3_URI}') LIMIT 5").fetchall()
        t1 = time.perf_counter()
        duration = (t1 - t0) * 1000
        print(f"Result: {len(res)} rows")
        print(f"Sample: {res}")
        print(f"Sample: {res}")
        print(f"Duration: {duration:.2f}ms")

        print("\n--- Test 3: Glob Scan (~891 files) ---")
        glob_path = f"s3://{BUCKET}/dumped-clustred-data/source_data_iceberg/data/ARDV=2026-02-01T00%3A00Z/**/*.parquet"
        print(f"Glob: {glob_path}")
        t0 = time.perf_counter()
        # fetching count across ~900 files
        res = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{glob_path}')").fetchall()
        t1 = time.perf_counter()
        duration = (t1 - t0) * 1000
        print(f"Result: {res[0][0]} rows")
        print(f"Duration: {duration:.2f}ms")

if __name__ == "__main__":
    asyncio.run(main())

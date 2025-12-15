import asyncio
import sys
import time
from pathlib import Path

# Add src to path
sys.path.append(str(Path.cwd()))

from src.lib.duckdb_client import get_pool, init_pool
from src.lib.iceberg_utils import get_latest_metadata_file
from src.lib.valkey_cache import init_valkey_cache


async def run_join_demo() -> None:
    print("Initializing resources...")
    init_pool()
    await init_valkey_cache()

    # 1. Get the Iceberg Path
    # "Fact Table"
    resolution = await get_latest_metadata_file(
        "s3://liquid-crystal-bucket-manoj/dumped-clustred-data/source_data_iceberg"
    )
    metadata_path = resolution["data"]
    print(f"Iceberg Source: {metadata_path}")

    pool = get_pool()

    # 2. Acquire Connection
    # EVERYTHING inside this block happens on the SAME separate DuckDB instance
    async with pool.connection() as conn:
        print("\n--- Step 1: Create Local Dimension Table (in-memory) ---")
        # Creating a temporary table mapping POS_CD (Point of Sale Code) to Country Names
        # This simulates joining a "Dimension" table
        await asyncio.to_thread(
            conn.execute,
            """
            CREATE TEMP TABLE pos_dimensions (
                code VARCHAR,
                country_name VARCHAR,
                region VARCHAR
            );
            INSERT INTO pos_dimensions VALUES 
                ('UK', 'United Kingdom', 'EMEA'),
                ('US', 'United States', 'NA'),
                ('DE', 'Germany', 'EMEA');
        """,
        )
        print("Local table 'pos_dimensions' created.")

        print("\n--- Step 2: Join Iceberg (S3) with Local Table ---")
        # We will join the remote Iceberg table on POS_CD = code
        query = f"""
            SELECT 
                d.country_name,
                d.region,
                COUNT(*) as transaction_count
            FROM iceberg_scan('{metadata_path}') as f
            JOIN pos_dimensions d ON f.POS_CD = d.code
            WHERE f.ARDV = '2026-05-31'  -- Filter partition for speed
            GROUP BY d.country_name, d.region
            ORDER BY transaction_count DESC
        """  # nosec B608

        t0 = time.perf_counter()
        await asyncio.to_thread(conn.execute, query)
        rows = await asyncio.to_thread(conn.fetchall)
        t1 = time.perf_counter()

        print(f"Join completed in {(t1 - t0) * 1000:.2f}ms")
        print("\nResults:")
        print(f"{'Country':<20} | {'Region':<10} | {'Count':<10}")
        print("-" * 45)
        for row in rows:
            print(f"{row[0]:<20} | {row[1]:<10} | {row[2]:<10}")

    print("\n--- Step 3: S3-to-S3 Join (Self-Join Simulation) ---")
    # Simulating joining two large S3 tables.
    # Here we alias the SAME table as 'a' and 'b', but DuckDB treats them as two scans.
    # This proves that DuckDB pulls required data from both S3 sources and joins locally.
    s3_join_query = f"""
        SELECT 
            a.POS_CD,
            COUNT(*) as correlated_count
        FROM iceberg_scan('{metadata_path}') as a
        JOIN iceberg_scan('{metadata_path}') as b 
            ON a.POS_CD = b.POS_CD 
            AND a.ARDV = b.ARDV 
        WHERE a.ARDV = '2026-05-31' 
          AND a.SHOP_CAR_TYPE_CD = 'XXAR'
          AND b.SHOP_CAR_TYPE_CD = 'XXAR'
        GROUP BY a.POS_CD
        LIMIT 5
    """  # nosec B608

    t0 = time.perf_counter()
    async with pool.connection() as conn:
        # Note: In a real scenario, we might parallelize the scans,
        # but the JOIN happens in the single DuckDB engine.
        await asyncio.to_thread(conn.execute, s3_join_query)
        rows_s3 = await asyncio.to_thread(conn.fetchall)
    t1 = time.perf_counter()

    print(f"S3-to-S3 Join completed in {(t1 - t0) * 1000:.2f}ms")
    print(f"Result: {rows_s3}")


if __name__ == "__main__":
    asyncio.run(run_join_demo())

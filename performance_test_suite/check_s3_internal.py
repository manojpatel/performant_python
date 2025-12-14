import asyncio
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

try:
    from performance_test_suite.iceberg_runner import run_iceberg_benchmarks
    from src.lib.duckdb_client import init_pool
    from src.lib.valkey_cache import init_valkey_cache
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

async def main():
    print("Checking S3 connectivity via Iceberg...")
    
    # Check env vars
    print("Environment Variables:")
    for key in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"]:
        val = os.getenv(key)
        masked = "***" if val else "None"
        if key == "AWS_REGION" and val: masked = val
        print(f"  {key}: {masked}")

    # Init pool
    print("Initializing DuckDB pool...")
    init_pool()
    
    # Init Cache
    print("Initializing Valkey cache...")
    await init_valkey_cache()

    try:
        results = await run_iceberg_benchmarks()
        for res in results:
            print(f"{res.test_name}: {res.duration_ms:.2f}ms")
            if res.duration_ms == 0.0:
                 print(f"Error: {res.result_summary}")
    except Exception as e:
        print(f"Fatal Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

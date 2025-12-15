import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path.cwd()))

from src.lib.duckdb_client import init_pool
from src.lib.valkey_cache import init_valkey_cache
from src.samples.samples_routes import benchmark_iceberg


async def test_iceberg_function() -> None:
    print("Testing Iceberg logic directly (bypassing HTTP layer)...")

    # Init dependencies
    init_pool()
    await init_valkey_cache()

    try:
        results = await benchmark_iceberg()
        print("SUCCESS: Function returned results")
        print("Performance Metrics:")
        for res in results:
            # Pydantic model access
            print(f"  - {res.test_name}: {res.duration_ms:.2f}ms")
            if res.duration_ms == 0.0:
                print(f"    Error: {res.result_summary}")
    except Exception as e:
        print(f"FAILURE: Exception during execution: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_iceberg_function())

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from src.lib.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Application Lifespan & Setup
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("application_startup", stage="starting")

    # Initialize Valkey cache
    from src.lib.valkey_cache import init_valkey_cache

    await init_valkey_cache()
    logger.info("valkey_initialized")

    # Initialize DuckDB connection pool
    from src.lib.duckdb_client import init_pool

    init_pool(database=":memory:", pool_size=20)
    logger.info("duckdb_pool_initialized", database=":memory:", pool_size=20)

    # Initialize Search Index (for samples)
    import asyncio

    from src.samples.extras import SearchEngine

    logger.info("search_index_seeding", documents=10000)
    await asyncio.to_thread(SearchEngine.get_instance().seed, 10000)
    logger.info("search_index_ready")
    # Initialize PostgreSQL
    from src.lib.postgres_client import init_postgres

    await init_postgres()
    logger.info("postgres_initialized")

    yield

    # Cleanup
    from src.lib.postgres_client import get_postgres
    from src.lib.valkey_cache import get_valkey_cache

    await get_valkey_cache().close()
    await get_postgres().close()
    logger.info("application_shutdown", stage="cleanup_complete")


# =============================================================================
# Create App
# =============================================================================

# Initialize tracing
from src.middleware.telemetry import init_tracing, instrument_fastapi  # noqa: E402

init_tracing()

app = FastAPI(
    title="Performant Python Demo", default_response_class=ORJSONResponse, lifespan=lifespan
)

# Instrument for tracing
instrument_fastapi(app)

# Add compression middleware
from src.middleware.compression import ZstdMiddleware  # noqa: E402

app.add_middleware(ZstdMiddleware, minimum_size=1000, compression_level=3)

# Add Request ID Middleware (should be early in the stack)
from src.middleware.log_correlation import RequestIdMiddleware  # noqa: E402

app.add_middleware(RequestIdMiddleware)


# =============================================================================
# Core Routes
# =============================================================================


@app.get("/")
async def root():
    """Health check / root endpoint."""
    return {
        "message": "Performant Python API",
        "status": "running",
        "stack": "FastAPI + Granian + PostgreSQL + Valkey",
        "endpoints": {
            "samples": "/samples (all demo/test/benchmark endpoints)",
            "postgres": "/events, /analytics/* (PostgreSQL production endpoints)",
        },
    }


# =============================================================================
# Include Routes
# =============================================================================

# Include all sample/testing routes under /samples prefix
from src.samples.samples_routes import router as samples_router  # noqa: E402

app.include_router(samples_router, prefix="/samples")


# =============================================================================
# Server Entry Point
# =============================================================================

if __name__ == "__main__":
    import granian

    print("Starting Granian server...")
    granian.Granian(
        target="src.main:app", address="0.0.0.0", port=8080, interface="asgi", workers=1, threads=1  # nosec B104
    ).serve()

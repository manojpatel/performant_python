from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from contextlib import asynccontextmanager


# =============================================================================
# Application Lifespan & Setup
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    print("🚀 application starting up...")
    
    # Initialize Valkey cache
    from src.lib.valkey_cache import init_valkey_cache
    await init_valkey_cache()
    print("🟣 Valkey cache initialized")
    
    # Initialize DuckDB connection pool
    from src.lib.duckdb_client import init_pool
    init_pool(database=":memory:", pool_size=4)
    print("💾 DuckDB connection pool initialized")
    
    # Initialize Search Index (for samples)
    import asyncio
    from src.samples.extras import SearchEngine
    print("🔎 Seeding search index...")
    await asyncio.to_thread(SearchEngine.get_instance().seed, 10000)
    
    # Initialize PostgreSQL
    from src.lib.postgres_client import init_postgres
    await init_postgres()
    print("🐘 PostgreSQL initialized")
    
    yield
    
    # Cleanup
    from src.lib.valkey_cache import get_cache
    from src.lib.postgres_client import get_postgres
    await get_cache().close()
    await get_postgres().close()
    print("🛑 application shutting down...")


# =============================================================================
# Create App
# =============================================================================

# Initialize tracing
from src.middleware.telemetry import init_tracing, instrument_fastapi
init_tracing()

app = FastAPI(
    title="Performant Python Demo",
    default_response_class=ORJSONResponse,
    lifespan=lifespan
)

# Instrument for tracing
instrument_fastapi(app)

# Add compression middleware
from src.middleware.compression import ZstdMiddleware
app.add_middleware(
    ZstdMiddleware,
    minimum_size=1000,
    compression_level=3
)


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
            "postgres": "/events, /analytics/* (PostgreSQL production endpoints)"
        }
    }


# =============================================================================
# Include Routes
# =============================================================================

# Include all sample/testing routes under /samples prefix
from src.samples.samples_routes import router as samples_router
app.include_router(samples_router, prefix="/samples")


# =============================================================================
# Server Entry Point
# =============================================================================

if __name__ == "__main__":
    import granian
    print("Starting Granian server...")
    granian.Granian(
        target="src.main:app",
        address="0.0.0.0",
        port=8080,
        interface="asgi",
        workers=1,
        threads=1
    ).serve()

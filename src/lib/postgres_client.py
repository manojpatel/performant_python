"""
PostgreSQL client module with asyncpg connection pooling.
Provides high-performance async database operations for user events analytics.

asyncpg is the fastest PostgreSQL driver for Python (2-3x faster than psycopg).
"""

import asyncio
import os
from typing import Any

import asyncpg
from opentelemetry import trace

from src.lib.logger import get_logger

logger = get_logger(__name__)

tracer = trace.get_tracer("performant-python.postgres")


class PostgresPool:
    """
    PostgreSQL connection pool manager using asyncpg.

    Features:
    - Connection pooling (10-20 connections)
    - Automatic retry with exponential backoff
    - Query instrumentation with OpenTelemetry
    - Prepared statements for performance
    """

    def __init__(self, url: str = "postgresql://performant:secretpass@localhost:5432/analytics"):
        self.url = url
        self._pool: asyncpg.Pool | None = None

    async def init_pool(self, min_size: int = 5, max_size: int = 20):
        """
        Initialize asyncpg connection pool.

        Args:
            min_size: Minimum number of connections in the pool
            max_size: Maximum number of connections in the pool
        """
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                self._pool = await asyncpg.create_pool(
                    self.url,
                    min_size=min_size,
                    max_size=max_size,
                    command_timeout=60,
                    server_settings={"application_name": "performant-python"},
                )

                # Test connection
                async with self._pool.acquire() as conn:
                    version = await conn.fetchval("SELECT version()")
                    logger.info(
                        "postgres_connected",
                        version=version.split(",")[0],
                        min_size=min_size,
                        max_size=max_size,
                    )

                    # Get table stats
                    count = await conn.fetchval("SELECT COUNT(*) FROM user_events")
                    logger.info("postgres_table_stats", table="user_events", row_count=count)

                return

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        "postgres_connection_retry",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        retry_delay=retry_delay,
                        error=str(e),
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(
                        "postgres_connection_failed",
                        attempts=max_retries,
                        error=str(e),
                        message="Database features will be disabled",
                        exc_info=True,
                    )

    async def close(self):
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("postgres_pool_closed")

    async def execute(self, query: str, *args) -> str:
        """
        Execute a query that doesn't return results (INSERT, UPDATE, DELETE).

        Returns:
            Command status (e.g., "INSERT 0 1")
        """
        if not self._pool:
            raise RuntimeError("PostgreSQL pool not initialized")

        with tracer.start_as_current_span("postgres_execute"):
            async with self._pool.acquire() as conn:
                return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> list[asyncpg.Record]:
        """
        Fetch multiple rows.

        Returns:
            List of Record objects (dict-like)
        """
        if not self._pool:
            raise RuntimeError("PostgreSQL pool not initialized")

        with tracer.start_as_current_span("postgres_fetch"):
            async with self._pool.acquire() as conn:
                return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> asyncpg.Record | None:
        """Fetch a single row."""
        if not self._pool:
            raise RuntimeError("PostgreSQL pool not initialized")

        with tracer.start_as_current_span("postgres_fetchrow"):
            async with self._pool.acquire() as conn:
                return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args) -> Any:
        """Fetch a single value."""
        if not self._pool:
            raise RuntimeError("PostgreSQL pool not initialized")

        with tracer.start_as_current_span("postgres_fetchval"):
            async with self._pool.acquire() as conn:
                return await conn.fetchval(query, *args)


# Global PostgreSQL connection pool instance
_pg_pool: PostgresPool | None = None


def get_postgres() -> PostgresPool:
    """Get the global PostgreSQL pool instance."""
    if _pg_pool is None:
        raise RuntimeError("PostgreSQL pool not initialized. Call init_postgres() first.")
    return _pg_pool


async def init_postgres(url: str | None = None) -> PostgresPool:
    """Initialize the global PostgreSQL connection pool."""
    global _pg_pool
    if url is None:
        url = os.getenv(
            "POSTGRES_URL", "postgresql://performant:secretpass@localhost:5432/analytics"
        )

    _pg_pool = PostgresPool(url)
    await _pg_pool.init_pool(min_size=5, max_size=20)
    return _pg_pool

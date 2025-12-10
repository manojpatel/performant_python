"""
Database connection pool for DuckDB.
Thread-safe connection pooling to avoid recreating connections.
"""
import duckdb
import asyncio
from queue import Queue, Empty
from contextlib import asynccontextmanager
from typing import Optional


class DuckDBConnectionPool:
    """Thread-safe DuckDB connection pool."""
    
    def __init__(self, database: str = ":memory:", pool_size: int = 4):
        self.database = database
        self.pool_size = pool_size
        self._pool: Queue = Queue(maxsize=pool_size)
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Create initial pool of connections."""
        for _ in range(self.pool_size):
            conn = duckdb.connect(self.database)
            self._pool.put(conn)
    
    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get a connection from the pool (blocking)."""
        try:
            return self._pool.get(timeout=5.0)
        except Empty:
            raise RuntimeError("Connection pool exhausted - no connections available")
    
    def _return_connection(self, conn: duckdb.DuckDBPyConnection):
        """Return a connection to the pool."""
        self._pool.put(conn)
    
    @asynccontextmanager
    async def connection(self):
        """
        Async context manager for getting a pooled connection.
        
        Usage:
            async with pool.connection() as conn:
                result = await asyncio.to_thread(conn.execute, "SELECT 1")
        """
        conn = await asyncio.to_thread(self._get_connection)
        try:
            yield conn
        finally:
            await asyncio.to_thread(self._return_connection, conn)
    
    def close_all(self):
        """Close all connections in the pool."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Empty:
                break


# Global pool instance (initialized in main.py)
_pool: Optional[DuckDBConnectionPool] = None


def get_pool() -> DuckDBConnectionPool:
    """Get the global connection pool instance."""
    if _pool is None:
        raise RuntimeError("Connection pool not initialized. Call init_pool() first.")
    return _pool


def init_pool(database: str = ":memory:", pool_size: int = 4) -> DuckDBConnectionPool:
    """Initialize the global connection pool."""
    global _pool
    _pool = DuckDBConnectionPool(database, pool_size)
    return _pool

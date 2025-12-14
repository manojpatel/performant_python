"""
Database connection pool for DuckDB.
Thread-safe connection pooling to avoid recreating connections.
"""
import duckdb
import asyncio
from queue import Queue, Empty
from contextlib import asynccontextmanager
from typing import Optional

from src.lib.logger import get_logger

logger = get_logger(__name__)


class DuckDBConnectionPool:
    """Thread-safe DuckDB connection pool."""
    
    def __init__(self, database: str = ":memory:", pool_size: int = 4, config: dict = None):
        self.database = database
        self.pool_size = pool_size
        self.config = config or {}
        self._pool: Queue = Queue(maxsize=pool_size)
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Create initial pool of connections."""
        import os
        for _ in range(self.pool_size):
            conn = duckdb.connect(self.database, config=self.config)
            # Install and load required extensions
            try:
                conn.execute("INSTALL httpfs; LOAD httpfs;")
                conn.execute("INSTALL iceberg; LOAD iceberg;")
                conn.execute("INSTALL aws; LOAD aws;")
                
                # Prefer explicit env vars to avoid IMDSv2 hangs in Docker
                if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
                    conn.execute(f"SET s3_access_key_id='{os.getenv('AWS_ACCESS_KEY_ID')}';")
                    conn.execute(f"SET s3_secret_access_key='{os.getenv('AWS_SECRET_ACCESS_KEY')}';")
                    conn.execute(f"SET s3_region='{os.getenv('AWS_REGION', 'us-east-1')}';")
                else:
                    conn.execute("CALL load_aws_credentials();")
            except Exception as e:
                print(f"Warning: Failed to load DuckDB extensions: {e}")
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


# Global DuckDB connection pool instance
_duckdb_pool: Optional[DuckDBConnectionPool] = None


def get_pool() -> DuckDBConnectionPool:
    """
    Get the global DuckDB connection pool instance.
    Raises RuntimeError if not initialized.
    """
    if _duckdb_pool is None:
        raise RuntimeError("DuckDB pool not initialized. Call init_pool() first.")
    return _duckdb_pool


def init_pool(database: str = ":memory:", pool_size: int = 4, config: dict = None) -> DuckDBConnectionPool:
    """
    Initialize the global DuckDB connection pool.
    """
    global _duckdb_pool
    _duckdb_pool = DuckDBConnectionPool(database, pool_size, config)
    return _duckdb_pool

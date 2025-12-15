"""
Valkey cache module with generic decorator for LRU caching.
Provides timing instrumentation and automatic fallback on cache miss.

Valkey is a high-performance Redis fork with improved performance and features.
Using xxhash for fast non-cryptographic cache key hashing.
"""

import asyncio
import json
import os
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

import orjson
import valkey.asyncio as valkey
import xxhash
from opentelemetry import trace

from src.lib.logger import get_logger

logger = get_logger(__name__)

tracer = trace.get_tracer("performant-python.valkey-cache")


class ValkeyCache:
    """Valkey connection pool and cache management."""

    def __init__(self, url: str = "valkey://localhost:6379"):
        self.url = url
        self._pool: valkey.Valkey | None = None

    async def init_pool(self) -> None:
        """Initialize Valkey connection pool."""
        self._pool = valkey.Valkey.from_url(
            self.url,
            encoding="utf-8",
            decode_responses=False,  # We'll handle binary data with orjson
            max_connections=10,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        # Test connection
        if self._pool:
            try:
                await self._pool.ping()
                logger.info("valkey_connected", url=self.url, max_connections=10)
            except Exception as e:
                logger.warning(
                    "valkey_connection_failed",
                    url=self.url,
                    error=str(e),
                    message="Cache will be disabled",
                )

    async def close(self) -> None:
        """Close Valkey connection pool."""
        if self._pool:
            await self._pool.close()

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if not self._pool:
            return None

        try:
            with tracer.start_as_current_span("valkey_get"):
                data = await self._pool.get(key)
                if data:
                    return orjson.loads(data)
                return None
        except Exception as e:
            logger.error("valkey_get_error", key=key, error=str(e), exc_info=True)
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in cache with TTL (seconds)."""
        if not self._pool:
            return

        try:
            with tracer.start_as_current_span("valkey_set"):
                serialized = orjson.dumps(value)
                await self._pool.setex(key, ttl, serialized)
        except Exception as e:
            logger.error("valkey_set_error", key=key, ttl=ttl, error=str(e), exc_info=True)

    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        if not self._pool:
            return

        try:
            await self._pool.delete(key)
        except Exception as e:
            logger.error("valkey_delete_error", key=key, error=str(e), exc_info=True)


# Global cache instance
_valkey_cache: ValkeyCache | None = None


def get_valkey_cache() -> ValkeyCache:
    """Get the global Valkey cache instance."""
    if _valkey_cache is None:
        raise RuntimeError("Valkey cache not initialized. Call init_valkey_cache() first.")
    return _valkey_cache


async def init_valkey_cache(url: str | None = None) -> ValkeyCache:
    """Initialize the global Valkey cache."""
    global _valkey_cache
    if url is None:
        url = os.getenv("VALKEY_URL", "valkey://localhost:6379")

    _valkey_cache = ValkeyCache(url)
    await _valkey_cache.init_pool()
    return _valkey_cache


def generate_cache_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    """
    Generate a deterministic cache key from function arguments.
    Uses xxhash for ultra-fast non-cryptographic hashing.

    Args:
        prefix: Key prefix (typically function name)
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        xxhash-based cache key (10x faster than SHA256)
    """
    # Create a deterministic string representation
    key_data = {
        "args": args,
        "kwargs": sorted(kwargs.items()),  # Sort for determinism
    }
    key_string = json.dumps(key_data, sort_keys=True, default=str)
    # Use xxhash64 for speed (non-cryptographic but perfect for cache keys)
    key_hash = xxhash.xxh64(key_string.encode()).hexdigest()[:16]

    return f"{prefix}:{key_hash}"


def valkey_cache(
    ttl: int = 300, key_prefix: str | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Generic Valkey cache decorator with timing instrumentation.

    Usage:
        @valkey_cache(ttl=300, key_prefix="batch_stats")
        async def expensive_function(batch_id: str, data: list):
            # ... expensive computation
            return result

    The decorator will:
    1. Generate a cache key from function name + arguments (using xxhash)
    2. Check Valkey for cached result (timed)
    3. Return cached result if found (cache hit)
    4. Call the wrapped function if not found (cache miss)
    5. Store the result in Valkey with TTL
    6. Return result with cache metadata

    Args:
        ttl: Time-to-live in seconds (default: 300)
        key_prefix: Custom key prefix (default: function name)

    Returns:
        Dictionary with:
            - data: The actual result
            - cache_hit: Boolean indicating cache hit/miss
            - cache_time_ms: Time spent checking cache
            - source: "valkey" or function source
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            cache = get_valkey_cache()
            prefix = key_prefix or func.__name__

            # Generate cache key
            cache_key = generate_cache_key(prefix, *args, **kwargs)

            # Try to get from cache
            cache_start = time.perf_counter()
            cached_result = await cache.get(cache_key)
            cache_time = (time.perf_counter() - cache_start) * 1000

            if cached_result is not None:
                # Cache hit
                return {
                    "data": cached_result,
                    "cache_hit": True,
                    "cache_time_ms": cache_time,
                    "source": "valkey",
                }

            # Cache miss - call the wrapped function
            with tracer.start_as_current_span(f"{func.__name__}_cache_miss"):
                result = await func(*args, **kwargs)

            # Store in cache asynchronously (don't wait)
            asyncio.create_task(cache.set(cache_key, result, ttl))

            return {
                "data": result,
                "cache_hit": False,
                "cache_time_ms": cache_time,
                "source": "duckdb",  # or whatever the actual source is
            }

        return wrapper

    return decorator


# Alias for backward compatibility and internal usage

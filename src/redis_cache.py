"""
Redis cache module with generic decorator for LRU caching.
Provides timing instrumentation and automatic fallback on cache miss.
"""
import os
import time
import asyncio
import hashlib
import json
from typing import Any, Callable, Optional
from functools import wraps

import redis.asyncio as redis
import orjson
from opentelemetry import trace

tracer = trace.get_tracer("performant-python.redis-cache")


class RedisCache:
    """Redis connection pool and cache management."""
    
    def __init__(self, url: str = "redis://localhost:6379"):
        self.url = url
        self._pool: Optional[redis.Redis] = None
    
    async def init_pool(self):
        """Initialize Redis connection pool."""
        self._pool = redis.Redis.from_url(
            self.url,
            encoding="utf-8",
            decode_responses=False,  # We'll handle binary data with orjson
            max_connections=10,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        # Test connection
        try:
            await self._pool.ping()
            print(f"✅ Redis connected at {self.url}")
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e}. Cache will be disabled.")
    
    async def close(self):
        """Close Redis connection pool."""
        if self._pool:
            await self._pool.close()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self._pool:
            return None
        
        try:
            with tracer.start_as_current_span("redis_get"):
                data = await self._pool.get(key)
                if data:
                    return orjson.loads(data)
                return None
        except Exception as e:
            print(f"Redis GET error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 300):
        """Set value in cache with TTL (seconds)."""
        if not self._pool:
            return
        
        try:
            with tracer.start_as_current_span("redis_set"):
                serialized = orjson.dumps(value)
                await self._pool.setex(key, ttl, serialized)
        except Exception as e:
            print(f"Redis SET error for key {key}: {e}")
    
    async def delete(self, key: str):
        """Delete key from cache."""
        if not self._pool:
            return
        
        try:
            await self._pool.delete(key)
        except Exception as e:
            print(f"Redis DELETE error for key {key}: {e}")


# Global cache instance
_cache: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """Get the global Redis cache instance."""
    if _cache is None:
        raise RuntimeError("Redis cache not initialized. Call init_cache() first.")
    return _cache


async def init_cache(url: Optional[str] = None) -> RedisCache:
    """Initialize the global Redis cache."""
    global _cache
    if url is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    _cache = RedisCache(url)
    await _cache.init_pool()
    return _cache


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate a deterministic cache key from function arguments.
    
    Args:
        prefix: Key prefix (typically function name)
        *args: Positional arguments
        **kwargs: Keyword arguments
    
    Returns:
        SHA256 hash-based cache key
    """
    # Create a deterministic string representation
    key_data = {
        "args": args,
        "kwargs": sorted(kwargs.items())  # Sort for determinism
    }
    key_string = json.dumps(key_data, sort_keys=True, default=str)
    key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]
    
    return f"{prefix}:{key_hash}"


def redis_cache(ttl: int = 300, key_prefix: Optional[str] = None):
    """
    Generic Redis cache decorator with timing instrumentation.
    
    Usage:
        @redis_cache(ttl=300, key_prefix="batch_stats")
        async def expensive_function(batch_id: str, data: list):
            # ... expensive computation
            return result
    
    The decorator will:
    1. Generate a cache key from function name + arguments
    2. Check Redis for cached result (timed)
    3. Return cached result if found (cache hit)
    4. Call the wrapped function if not found (cache miss)
    5. Store the result in Redis with TTL
    6. Return result with cache metadata
    
    Args:
        ttl: Time-to-live in seconds (default: 300)
        key_prefix: Custom key prefix (default: function name)
    
    Returns:
        Dictionary with:
            - data: The actual result
            - cache_hit: Boolean indicating cache hit/miss
            - cache_time_ms: Time spent checking cache
            - source: "redis" or function source
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()
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
                    "source": "redis"
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
                "source": "duckdb"  # or whatever the actual source is
            }
        
        return wrapper
    return decorator

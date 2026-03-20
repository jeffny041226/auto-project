"""Redis connection management."""
import json
from typing import Any, Optional

import redis.asyncio as redis

from app.config import settings


class RedisClient:
    """Async Redis client wrapper."""

    def __init__(self):
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Initialize Redis connection pool."""
        self._pool = redis.ConnectionPool.from_url(
            settings.get_redis_url(),
            decode_responses=True,
            max_connections=50,
        )
        self._client = redis.Redis(connection_pool=self._pool)

    async def close(self) -> None:
        """Close Redis connections."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()

    @property
    def client(self) -> redis.Redis:
        """Get Redis client."""
        if not self._client:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        return await self.client.get(key)

    async def set(
        self,
        key: str,
        value: str,
        expire: Optional[int] = None,
    ) -> bool:
        """Set key-value pair with optional expiration."""
        return await self.client.set(key, value, ex=expire)

    async def delete(self, key: str) -> int:
        """Delete key."""
        return await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return await self.client.exists(key) > 0

    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value by key."""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None

    async def set_json(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None,
    ) -> bool:
        """Set JSON value by key."""
        return await self.set(key, json.dumps(value), expire=expire)

    async def incr(self, key: str) -> int:
        """Increment value."""
        return await self.client.incr(key)

    async def decr(self, key: str) -> int:
        """Decrement value."""
        return await self.client.decr(key)

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key."""
        return await self.client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        """Get TTL of key."""
        return await self.client.ttl(key)

    async def keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern."""
        return await self.client.keys(pattern)

    async def hset(self, name: str, key: str, value: str) -> int:
        """Set hash field."""
        return await self.client.hset(name, key, value)

    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field."""
        return await self.client.hget(name, key)

    async def hgetall(self, name: str) -> dict[str, str]:
        """Get all hash fields."""
        return await self.client.hgetall(name)

    async def lpush(self, key: str, *values: str) -> int:
        """Push to list."""
        return await self.client.lpush(key, *values)

    async def rpop(self, key: str) -> Optional[str]:
        """Pop from list."""
        return await self.client.rpop(key)

    async def llen(self, key: str) -> int:
        """Get list length."""
        return await self.client.llen(key)


# Global Redis client instance
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """Dependency to get Redis client."""
    return redis_client

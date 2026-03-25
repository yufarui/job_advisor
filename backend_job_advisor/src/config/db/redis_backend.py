from __future__ import annotations

import redis.asyncio as redis

from config.base_conifg import Settings


class RedisDb:
    """组合根里 `redis_db = RedisDb(settings)`，再 `SomeService(redis_db)`。"""

    def __init__(self, settings: Settings) -> None:
        self._pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._client = redis.Redis(connection_pool=self._pool)

    @property
    def client(self) -> redis.Redis:
        return self._client

    async def connect(self) -> None:
        await self._client.ping()

    async def aclose(self) -> None:
        await self._client.aclose()
        await self._pool.disconnect()

"""Redis 工具结果缓存：供 Review 写入、Executor 读取。"""

from __future__ import annotations

import json
from typing import Any

from config.db.redis_backend import RedisDb
from config.log_config import log_io


class ToolResultCacheStorage:
    """``ToolResultCachePort`` 的 Redis 实现。"""

    def __init__(
        self,
        redis: RedisDb,
        *,
        key_prefix: str = "cache:tool_result",
        default_ttl_seconds: int = 3600,
    ) -> None:
        self._redis = redis
        self._prefix = key_prefix.strip() or "cache:tool_result"
        self._default_ttl = max(1, int(default_ttl_seconds))

    def _key(self, key: str) -> str:
        k = key.strip()
        if not k:
            return self._prefix
        if k.startswith(f"{self._prefix}:"):
            return k
        return f"{self._prefix}:{k}"

    @log_io
    async def get(self, key: str) -> Any | None:
        full_key = self._key(key)
        raw = await self._redis.client.get(full_key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    @log_io
    async def set(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        full_key = self._key(key)
        ttl = self._default_ttl if ttl_seconds is None else max(1, int(ttl_seconds))
        payload = json.dumps(value, ensure_ascii=False, default=str)
        await self._redis.client.set(full_key, payload, ex=ttl)

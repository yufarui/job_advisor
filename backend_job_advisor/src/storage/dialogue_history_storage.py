"""用户短期对话历史（``user_history_dialogue``）：Redis List + TTL（设计文档 §7）。"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, cast

from motor.motor_asyncio import AsyncIOMotorCollection
from config.db.mongo_backend import MongoDb
from config.db.redis_backend import RedisDb
from config.log_config import log_io
from constants.biz_constant import BizConstant
from core.time_utils import now_shanghai
from entity.redis.dialogue_message import DialogueMessage

logger = logging.getLogger(__name__)


class DialogueHistoryStorage:
    """按 ``user_id`` 维度读写短期对话（Redis List + TTL）。

    - Key：``user:{user_id}:history``（与 task_id 无关）。
    - Value：Redis List，元素为 ``DialogueMessage`` 的 JSON 字符串；**RPUSH** 追加，时间正序
      （``LRANGE 0 -1`` 为从旧到新）。
    - 长度：仅保留最近 ``max_messages`` 条（先进先出，默认 10）。
    - TTL：每次写入后 ``EXPIRE``，默认 1 小时。
    """

    def __init__(
        self,
        redis: RedisDb,
        *,
        ttl_seconds: int = 3600,
        max_messages: int = 10,
        mongo: MongoDb | None = None,
    ) -> None:
        self._redis = redis
        self._ttl = max(1, int(ttl_seconds))
        self._max_messages = max(1, int(max_messages))
        self._mongo = mongo

    def _key(self, user_id: str) -> str:
        return f"user:{user_id.strip()}:history"

    def _mongo_coll(self) -> AsyncIOMotorCollection | None:
        if self._mongo is None:
            return None
        return self._mongo.database[BizConstant.DIALOGUE_HISTORY_COLLECTION]

    @log_io
    async def append(
        self,
        user_id: str,
        message: DialogueMessage,
        *,
        task_id: str | None = None,
    ) -> None:
        key = self._key(user_id)
        raw = message.to_redis_element()
        pipe = self._redis.client.pipeline()
        pipe.rpush(key, raw)
        pipe.ltrim(key, -self._max_messages, -1)
        pipe.expire(key, self._ttl)
        await pipe.execute()
        coll = self._mongo_coll()
        if coll is not None:
            now = now_shanghai()
            doc: dict[str, Any] = {
                "user_id": user_id.strip(),
                "task_id": (task_id or "").strip(),
                "role": message.role,
                "content": message.content,
                "ts": message.ts or now,
                "created_at": now,
            }
            await coll.insert_one(doc)
        logger.debug(
            "dialogue append key=%s len_msg=%s ttl=%s max=%s",
            key,
            len(raw),
            self._ttl,
            self._max_messages,
        )

    @log_io
    async def get_recent(
        self,
        user_id: str,
        *,
        limit: int,
    ) -> list[DialogueMessage]:
        """仅取最近 ``limit`` 条（仍按时间正序）。"""
        n = max(1, min(limit, 10_000))
        key = self._key(user_id)
        elements = await self._redis.client.lrange(key, -n, -1)
        if not elements:
            return []
        return DialogueMessage.load_many_from_list(list(elements))

    @log_io
    async def get_recent_days(
        self,
        user_id: str,
        *,
        days: int = 7,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        coll = self._mongo_coll()
        if coll is None:
            return []
        uid = user_id.strip()
        if not uid:
            return []
        d = max(1, min(int(days), 7))
        n = max(1, min(int(limit), 2000))
        since = now_shanghai() - timedelta(days=d)
        q = {"user_id": uid, "ts": {"$gte": since}}
        cur = coll.find(q).sort("ts", -1).limit(n)
        rows = [cast(dict[str, Any], x) async for x in cur]
        rows.reverse()
        return rows

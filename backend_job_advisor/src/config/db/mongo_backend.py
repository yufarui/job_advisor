from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorClientSession,
    AsyncIOMotorDatabase,
)

from config.base_conifg import Settings


class MongoDb:
    """组合根里 ``mongo = MongoDb(settings)``；事务需副本集或分片集群（单机 standalone 不支持）。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
        )
        self.db = self.client[settings.mongodb_db]

    @property
    def database(self) -> AsyncIOMotorDatabase:
        """与历史代码兼容，等价于 ``db``。"""
        return self.db

    async def connect(self) -> None:
        await self.db.command("ping")

    async def close(self) -> None:
        self.client.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncIOMotorClientSession]:
        """在事务内执行多文档写操作；``yield`` 的 session 需传给各 ``session=`` 参数。

        退出上下文时，无异常则提交，有异常则中止（由 Motor 的 ``start_transaction`` 上下文管理）。"""
        async with await self.client.start_session() as session:
            async with session.start_transaction():
                yield session

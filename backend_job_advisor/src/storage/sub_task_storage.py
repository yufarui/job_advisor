"""MongoDB ``sub_tasks`` 集合：Plan 持久化与 Review 调度读取。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast

from motor.motor_asyncio import AsyncIOMotorCollection

from config.log_config import log_io
from config.db.mongo_backend import MongoDb
from constants.biz_constant import BizConstant
from constants.sub_task_status_enum import SubTaskStatusEnum
from constants.sub_task_type_enum import SubTaskTypeEnum
from core.id_utils import generate_short_id
from entity.mongo.sub_task import SubTask

SHANGHAI_TZ = timezone(timedelta(hours=8))


def now_shanghai() -> datetime:
    return datetime.now(SHANGHAI_TZ)


class SubTaskStorage:
    def __init__(self, mongo: MongoDb) -> None:
        self._mongo = mongo

    def _coll(self) -> AsyncIOMotorCollection:
        return self._mongo.database[BizConstant.SUB_TASKS_COLLECTION]

    @log_io
    async def list_sub_tasks_by_task(self, task_id: str) -> list[SubTask]:
        tid = task_id.strip()
        if not tid:
            return []
        cursor = self._coll().find({"task_id": tid}).sort("created_at", 1)
        return [SubTask.from_mongo(cast(dict[str, Any], d)) async for d in cursor]

    @log_io
    async def list_open_sub_tasks(self, task_id: str) -> list[SubTask]:
        tid = task_id.strip()
        if not tid:
            return []
        q = {
            "task_id": tid,
            "status": {
                "$in": [
                    SubTaskStatusEnum.created.value,
                    SubTaskStatusEnum.waiting.value,
                ]
            },
        }
        cursor = self._coll().find(q).sort("created_at", 1)
        return [SubTask.from_mongo(cast(dict[str, Any], d)) async for d in cursor]

    @log_io
    async def get_sub_task(self, task_id: str, sub_task_id: str) -> SubTask | None:
        tid = task_id.strip()
        sid = sub_task_id.strip()
        if not tid or not sid:
            return None
        raw = await self._coll().find_one({"_id": sid, "task_id": tid})
        return SubTask.from_mongo(cast(dict[str, Any], raw)) if raw else None

    @log_io
    async def count_open_clarifies(self, task_id: str) -> int:
        tid = task_id.strip()
        if not tid:
            return 0
        return int(
            await self._coll().count_documents(
                {
                    "task_id": tid,
                    "task_type": SubTaskTypeEnum.tool_slot_clarify.value,
                    "status": {
                        "$in": [
                            SubTaskStatusEnum.created.value,
                            SubTaskStatusEnum.waiting.value,
                        ]
                    },
                }
            )
        )

    @log_io
    async def insert_sub_task(self, sub: SubTask) -> str:
        now = now_shanghai()
        sid = (sub.id or "").strip() or generate_short_id()
        row = sub.model_copy(
            update={
                "id": sid,
                "created_at": sub.created_at or now,
                "updated_at": now,
            }
        )
        doc = row.to_mongo()
        doc["_id"] = sid
        await self._coll().insert_one(doc)
        return sid

    @log_io
    async def update_sub_task_fields(
        self,
        task_id: str,
        sub_task_id: str,
        *,
        set_fields: dict[str, Any],
    ) -> bool:
        tid = task_id.strip()
        sid = sub_task_id.strip()
        if not tid or not sid or not set_fields:
            return False
        now = now_shanghai()
        payload = {**set_fields, "updated_at": now}
        r = await self._coll().update_one(
            {"_id": sid, "task_id": tid},
            {"$set": payload},
        )
        return r.modified_count > 0 or r.matched_count > 0

    @log_io
    async def set_sub_task_status(
        self,
        task_id: str,
        sub_task_id: str,
        status: str | SubTaskStatusEnum,
    ) -> bool:
        v = status.value if isinstance(status, SubTaskStatusEnum) else status
        return await self.update_sub_task_fields(
            task_id,
            sub_task_id,
            set_fields={"status": v},
        )

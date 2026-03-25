"""MongoDB ``tasks`` 集合：主任务生命周期，实现 ``TaskLifecyclePort``。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from motor.motor_asyncio import AsyncIOMotorCollection

from config.db.mongo_backend import MongoDb
from config.log_config import log_io
from constants.biz_constant import BizConstant
from core.id_utils import generate_short_id
from core.time_utils import now_shanghai
from entity.mongo.task import Task


class TaskStorage:
    """Triage 用：列出近期活跃主任务、新建主任务。"""

    def __init__(self, mongo: MongoDb) -> None:
        self._mongo = mongo

    def _coll(self) -> AsyncIOMotorCollection:
        return self._mongo.database[BizConstant.TASKS_COLLECTION]

    @log_io
    async def list_candidate_tasks(
        self,
        user_id: str,
        *,
        created_after: datetime,
        limit: int = 20,
    ) -> list[Task]:
        uid = user_id.strip()
        if not uid:
            return []
        q: dict[str, Any] = {
            "user_id": uid,
            "status": "active",
            "created_at": {"$gte": created_after},
        }
        cur = (
            self._coll()
            .find(q)
            .sort("created_at", -1)
            .limit(max(1, limit))
        )
        return [Task.from_mongo(cast(dict[str, Any], d)) async for d in cur]

    @log_io
    async def create_task(self, task: Task) -> str:
        now = now_shanghai()
        oid = (task.id or "").strip() or generate_short_id()
        row = task.model_copy(
            update={
                "id": oid,
                "created_at": task.created_at or now,
                "updated_at": task.updated_at or now,
            }
        )
        doc = row.to_mongo()
        if "_id" not in doc:
            doc["_id"] = oid
        await self._coll().insert_one(doc)
        return oid

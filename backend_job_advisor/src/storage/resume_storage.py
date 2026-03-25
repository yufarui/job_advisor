"""user_resume 集合：与用户 1:1（``user_id`` 唯一）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection

from config.db.mongo_backend import MongoDb
from config.log_config import log_io
from constants.biz_constant import BizConstant
from entity.mongo.user_resume import UserResume
from entity.view.resume_update_request import ResumeUpdateRequest

SHANGHAI_TZ = timezone(timedelta(hours=8))


def now_shanghai() -> datetime:
    return datetime.now(SHANGHAI_TZ)


class ResumeStorage:
    def __init__(self, mongo: MongoDb) -> None:
        self._mongo = mongo

    def _col(self) -> AsyncIOMotorCollection:
        return self._mongo.database[BizConstant.USER_RESUME_COLLECTION]

    @log_io
    async def find_by_user_id(self, user_id: str) -> UserResume | None:
        raw = await self._col().find_one({"user_id": user_id})
        return UserResume.from_mongo(raw) if raw else None

    @log_io
    async def upsert_resume(self, resume: UserResume) -> str:
        """按 ``user_id`` 整文档替换；保留已有 ``created_at``。"""
        now = now_shanghai()
        col = self._col()
        existing = await col.find_one({"user_id": resume.user_id})
        doc = resume.to_mongo()
        doc.pop("_id", None)
        doc["updated_at"] = now
        if existing:
            _id = existing["_id"]
            doc["created_at"] = (
                resume.created_at
                if resume.created_at is not None
                else existing.get("created_at")
            )
            replacement: dict[str, Any] = {**doc, "_id": _id}
            await col.replace_one({"user_id": resume.user_id}, replacement)
            return str(_id)
        doc["created_at"] = resume.created_at or now
        res = await col.insert_one(doc)
        return str(res.inserted_id)

    @log_io
    async def update_resume_by_user_id(self, body: ResumeUpdateRequest) -> bool:
        payload = body.to_mongo_set()
        if not payload:
            matched = await self._col().count_documents({"user_id": body.user_id}, limit=1)
            return matched > 0
        payload["updated_at"] = now_shanghai()
        r = await self._col().update_one({"user_id": body.user_id}, {"$set": payload})
        return r.modified_count > 0 or r.matched_count > 0

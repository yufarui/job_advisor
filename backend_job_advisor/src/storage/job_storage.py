"""jobs / user_jobs 的 MongoDB 基础访问；职位侧以 ``biz_id`` 为唯一业务键；返回领域模型。

本模块方法均为 ``async``：Motor（``AsyncIOMotorCollection``）的查询/写入在 asyncio 上是非阻塞 I/O，
必须与 ``await`` / ``async for`` 配合。业界在 FastAPI + Motor 下的常见做法是「仓储层全面 async」，
而不是改用同步 PyMongo + 线程池（除非遗留系统迁移）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast

from motor.motor_asyncio import AsyncIOMotorCollection

from config.log_config import log_io
from config.db.mongo_backend import MongoDb
from constants.biz_constant import BizConstant
from entity.mongo.job import Job
from entity.mongo.user_job import UserJob
from entity.mongo.user_job_query_filter import UserJobQueryFilter
from entity.view.job_update_request import JobUpdateRequest
from entity.view.user_job_update_request import UserJobUpdateRequest

SHANGHAI_TZ = timezone(timedelta(hours=8))


def now_shanghai() -> datetime:
    return datetime.now(SHANGHAI_TZ)


class JobStorage:
    def __init__(self, mongo: MongoDb) -> None:
        self._mongo = mongo

    def _jobs(self) -> AsyncIOMotorCollection:
        return self._mongo.database[BizConstant.JOBS_COLLECTION]

    def _user_jobs(self) -> AsyncIOMotorCollection:
        return self._mongo.database[BizConstant.USER_JOBS_COLLECTION]

    @log_io
    async def job_exists_by_biz_id(self, biz_id: str) -> bool:
        doc = await self._jobs().find_one({"biz_id": biz_id}, projection={"_id": 1})
        return doc is not None

    @log_io
    async def find_job_by_biz_id(self, biz_id: str) -> Job | None:
        """按业务唯一键查询单条职位。"""
        raw = await self._jobs().find_one({"biz_id": biz_id})
        return Job.from_mongo(raw) if raw else None

    @log_io
    async def find_jobs_by_biz_ids_ordered(self, biz_ids: list[str]) -> list[Job]:
        """按入参 ``biz_ids`` 顺序返回存在的职位。"""
        if not biz_ids:
            return []
        cursor = self._jobs().find({"biz_id": {"$in": biz_ids}})
        by_biz: dict[str, dict[str, Any]] = {}
        async for doc in cursor:
            b = doc.get("biz_id")
            if isinstance(b, str):
                by_biz[b] = cast(dict[str, Any], doc)
        return [
            Job.from_mongo(by_biz[b])
            for b in biz_ids
            if b in by_biz
        ]

    @log_io
    async def find_jobs_by_title_regex(
        self,
        title: str,
        *,
        limit: int = 1,
    ) -> list[Job]:
        q = {"title": {"$regex": title, "$options": "i"}}
        cursor = self._jobs().find(q).limit(max(1, limit))
        return [Job.from_mongo(d) async for d in cursor]

    @log_io
    async def find_jobs_by_biz_ids_and_created_range(
        self,
        biz_ids: list[str],
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[Job]:
        if not biz_ids:
            return []
        filt: dict[str, Any] = {"biz_id": {"$in": biz_ids}}
        if created_from is not None or created_to is not None:
            cr: dict[str, Any] = {}
            if created_from is not None:
                cr["$gte"] = created_from
            if created_to is not None:
                cr["$lte"] = created_to
            filt["created_at"] = cr
        cursor = self._jobs().find(filt).sort("created_at", -1)
        return [Job.from_mongo(d) async for d in cursor]

    @log_io
    async def insert_job(self, job: Job) -> str:
        doc = job.to_mongo()
        doc.pop("_id", None)
        res = await self._jobs().insert_one(doc)
        return str(res.inserted_id)

    @log_io
    async def update_job_by_biz_id(self, body: JobUpdateRequest) -> bool:
        payload = body.to_mongo_set()
        payload["updated_at"] = now_shanghai()
        result = await self._jobs().update_one({"biz_id": body.biz_id}, {"$set": payload})
        return result.modified_count > 0 or result.matched_count > 0

    @log_io
    async def find_user_job_by_user_and_biz(
        self,
        user_id: str,
        biz_id: str,
    ) -> UserJob | None:
        raw = await self._user_jobs().find_one(
            {"user_id": user_id, "job_id": biz_id},
        )
        return UserJob.from_mongo(raw) if raw else None

    @log_io
    async def find_user_jobs(self, query: UserJobQueryFilter) -> list[UserJob]:
        filt = query.to_mongo_filter()
        return [
            UserJob.from_mongo(d)
            async for d in self._user_jobs().find(filt)
        ]

    @log_io
    async def list_distinct_job_ids_for_user_status(
        self,
        user_id: str,
        status: str,
    ) -> list[str]:
        cur = self._user_jobs().find({"user_id": user_id, "status": status})
        out: list[str] = []
        seen: set[str] = set()
        async for doc in cur:
            jid = doc.get("job_id")
            if isinstance(jid, str) and jid not in seen:
                seen.add(jid)
                out.append(jid)
        return out

    @log_io
    async def update_user_job_by_user_and_biz(self, body: UserJobUpdateRequest) -> bool:
        payload = body.to_mongo_set()
        payload["updated_at"] = now_shanghai()
        result = await self._user_jobs().update_one(
            {"user_id": body.user_id, "job_id": body.biz_id},
            {"$set": payload},
        )
        return result.modified_count > 0 or result.matched_count > 0

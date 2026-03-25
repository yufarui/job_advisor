"""jobs / user_jobs：基于 JobStorage；页面查询返回 entity.view 模型。

服务层方法凡调用 ``JobStorage`` 的须为 ``async def``（底层 Motor I/O 均为异步）。
纯数据组装（如 ``to_user_job_card``）保持同步 ``def`` 即可。若希望减少 async 层级，
常见做法是保留仓储 async、路由直接依赖仓储（去掉 Service），而非把 Mongo 改成同步客户端。
"""

from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import Depends

from config.api.request_factory import get_mongo_db
from config.log_config import log_io
from constants.biz_constant import BizConstant
from constants.job_source_enum import JobSourceEnum
from constants.user_job_status_enum import UserJobStatusEnum
from core.time_utils import now_shanghai
from entity.mongo.job import Job
from entity.mongo.user_job import UserJob
from entity.mongo.user_job_query_filter import UserJobQueryFilter
from entity.view.job_update_request import JobUpdateRequest
from entity.view.user_job_card import UserJobCard
from entity.view.user_job_update_request import UserJobUpdateRequest
from entity.view.user_job_view import UserJobView
from storage import JobStorage, MongoDb


def _format_biz_id_candidate(letter: str) -> str:
    day = now_shanghai().strftime("%Y%m%d")
    tail = secrets.token_hex(3).upper()
    return f"JOB-{letter}-{day}-{tail}"


class JobService:
    def __init__(self, mongo: MongoDb) -> None:
        self._store = JobStorage(mongo)

    @staticmethod
    @log_io
    def to_user_job_card(job: Job, user_job: UserJob) -> UserJobCard:
        return UserJobCard(
            title=job.title,
            biz_id=job.biz_id,
            description=job.jd_text or "",
            status=user_job.status,
            attention_level=user_job.attention_level,
            salary=job.salary_range,
        )

    @log_io
    async def list_user_job_cards(
        self,
        *,
        user_id: str,
        status: UserJobStatusEnum | None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[UserJobCard]:
        """列表页：按 user_jobs 状态 + jobs.created_at 过滤，返回卡片视图。"""
        st = status.value if isinstance(status, UserJobStatusEnum) else status
        user_jobs = await self._store.find_user_jobs(
            UserJobQueryFilter(user_id=user_id, status=st),
        )
        if not user_jobs:
            return []
        biz_ids = list(dict.fromkeys(uj.job_id for uj in user_jobs if uj.job_id))
        jobs = await self._store.find_jobs_by_biz_ids_and_created_range(
            biz_ids,
            created_from=created_from,
            created_to=created_to,
        )
        uj_by_biz: dict[str, UserJob] = {}
        for uj in user_jobs:
            if uj.job_id not in uj_by_biz:
                uj_by_biz[uj.job_id] = uj

        cards: list[UserJobCard] = []
        for job in jobs:
            uj = uj_by_biz.get(job.biz_id)
            if uj is None:
                continue
            cards.append(self.to_user_job_card(job, uj))
        return cards

    @log_io
    async def get_user_job_view(self, user_id: str, biz_id: str) -> UserJobView | None:
        """详情页：按 ``biz_id`` 与用户关联取 Job + UserJob。"""
        uj = await self._store.find_user_job_by_user_and_biz(user_id, biz_id)
        if uj is None:
            return None
        job = await self._store.find_job_by_biz_id(biz_id)
        if job is None:
            return None
        return UserJobView(job=job, user_job=uj)

    @log_io
    async def generate_biz_id(self, *, source: JobSourceEnum | None = None) -> str:
        letter = BizConstant._BIZ_LETTER.get(source, "X") if source is not None else "X"
        for _ in range(32):
            cand = _format_biz_id_candidate(letter)
            if not await self._store.job_exists_by_biz_id(cand):
                return cand
        raise RuntimeError("biz_id 生成失败：重试次数用尽")

    @log_io
    async def search_jobs_with_biz_ids(self, biz_ids: list[str]) -> list[Job]:
        return await self._store.find_jobs_by_biz_ids_ordered(biz_ids)

    @log_io
    async def search_jobs_with_title(self, title: str, *, limit: int = 1) -> list[Job]:
        return await self._store.find_jobs_by_title_regex(title, limit=limit)

    async def search_jobs(
        self,
        *,
        user_id: str,
        status: UserJobStatusEnum,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[Job]:
        st = status.value if isinstance(status, UserJobStatusEnum) else status
        biz_ids = await self._store.list_distinct_job_ids_for_user_status(user_id, st)
        if not biz_ids:
            return []
        return await self._store.find_jobs_by_biz_ids_and_created_range(
            biz_ids,
            created_from=created_from,
            created_to=created_to,
        )

    @log_io
    async def get_by_biz_id(self, biz_id: str) -> Job | None:
        return await self._store.find_job_by_biz_id(biz_id)

    @log_io
    async def update_jobs_with_biz_id(self, body: JobUpdateRequest) -> bool:
        return await self._store.update_job_by_biz_id(body)

    @log_io
    async def insert_jobs(self, jobs: list[Job]) -> list[str]:
        inserted: list[str] = []
        now = now_shanghai()
        for job in jobs:
            j = job
            if not (j.biz_id and str(j.biz_id).strip()):
                new_biz = await self.generate_biz_id(source=j.source)
                j = j.model_copy(update={"biz_id": new_biz})
            if j.created_at is None:
                j = j.model_copy(update={"created_at": now})
            if j.updated_at is None:
                j = j.model_copy(update={"updated_at": now})
            oid = await self._store.insert_job(j)
            inserted.append(oid)
        return inserted

    @log_io
    async def update_user_jobs_with_biz_id(self, body: UserJobUpdateRequest) -> bool:
        return await self._store.update_user_job_by_user_and_biz(body)


def get_job_service(
    mongo: MongoDb = Depends(get_mongo_db),
) -> JobService:
    return JobService(mongo)

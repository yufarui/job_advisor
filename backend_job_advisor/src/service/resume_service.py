"""user_resume：基于 ResumeStorage；API 返回 ``ResumeView``。"""

from __future__ import annotations

from fastapi import Depends

from config.api.request_factory import get_mongo_db
from config.log_config import log_io
from entity.mongo.user_resume import UserResume
from entity.view.resume_update_request import ResumeUpdateRequest
from entity.view.resume_upload_request import ResumeUploadRequest
from entity.view.resume_view import ResumeView
from storage import MongoDb, ResumeStorage


class ResumeService:
    def __init__(self, mongo: MongoDb) -> None:
        self._store = ResumeStorage(mongo)

    @staticmethod
    @log_io
    def merge_upload(base: UserResume, body: ResumeUploadRequest) -> UserResume:
        """``body`` 中已传字段覆盖 ``base``；``pdf`` 等仅视图字段不入库。"""
        updates: dict = {}
        if body.basic_info is not None:
            updates["basic_info"] = body.basic_info
        if body.work_experience is not None:
            updates["work_experience"] = body.work_experience
        if body.education is not None:
            updates["education"] = body.education
        if body.skills is not None:
            updates["skills"] = body.skills
        if body.job_intent is not None:
            updates["job_intent"] = body.job_intent
        return base.model_copy(update=updates)

    @log_io
    async def get_resume_view(self, user_id: str) -> ResumeView | None:
        r = await self._store.find_by_user_id(user_id)
        if r is None:
            return None
        return ResumeView.model_validate(r.model_dump(mode="python"))

    @log_io
    async def upsert_resume_from_upload(self, body: ResumeUploadRequest) -> ResumeView:
        existing = await self._store.find_by_user_id(body.user_id)
        base = existing or UserResume(user_id=body.user_id)
        merged = self.merge_upload(base, body)
        await self._store.upsert_resume(merged)
        saved = await self._store.find_by_user_id(body.user_id)
        if saved is None:
            raise RuntimeError("resume upsert 后读取失败")
        return ResumeView.model_validate(saved.model_dump(mode="python"))

    @log_io
    async def update_resume(self, body: ResumeUpdateRequest) -> bool:
        return await self._store.update_resume_by_user_id(body)


def get_resume_service(
    mongo: MongoDb = Depends(get_mongo_db),
) -> ResumeService:
    return ResumeService(mongo)

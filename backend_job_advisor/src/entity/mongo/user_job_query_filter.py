"""构造查询 user_jobs 时的过滤条件（非持久化文档）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from constants.user_job_status_enum import UserJobStatusEnum


class UserJobQueryFilter(BaseModel):
    """与 Mongo 查询字典对应；仅含非空字段。"""

    model_config = ConfigDict(extra="ignore")

    user_id: str | None = Field(
        default=None,
        description="按用户 ID 过滤；空则不限",
    )
    status: UserJobStatusEnum | str | None = Field(
        default=None,
        description="按状态过滤（UserJobStatusEnum 或字符串）；空则不限",
    )
    job_id: str | None = Field(
        default=None,
        description="按职位业务键过滤，对应 jobs.biz_id / user_jobs.job_id",
    )

    def to_mongo_filter(self) -> dict[str, Any]:
        q: dict[str, Any] = {}
        if self.user_id is not None:
            q["user_id"] = self.user_id
        if self.status is not None:
            q["status"] = (
                self.status.value
                if isinstance(self.status, UserJobStatusEnum)
                else self.status
            )
        if self.job_id is not None:
            q["job_id"] = self.job_id
        return q

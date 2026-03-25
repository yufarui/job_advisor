"""Mongo ``user_jobs``：用户对职位的关系（状态、关注度、备注）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from constants.attention_level_enum import AttentionLevelEnum
from constants.user_job_status_enum import UserJobStatusEnum


class UserJob(BaseModel):
    """用户与某一职位的关联记录。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str | None = Field(
        default=None,
        description="Mongo _id 转字符串；读库时由 _id 填入",
    )
    user_id: str = Field(..., description="用户 ID")
    job_id: str = Field(
        ...,
        description="职位业务键，对应 jobs.biz_id",
    )
    status: UserJobStatusEnum = Field(
        default=UserJobStatusEnum.saved,
        description="用户侧进度（枚举 UserJobStatusEnum）",
    )
    attention_level: AttentionLevelEnum | None = Field(
        default=None,
        description="关注度（枚举 AttentionLevelEnum，1–5）",
    )
    note: str | None = Field(default=None, description="用户对该职位的备注")
    updated_at: datetime | None = Field(
        default=None,
        description="本条用户—职位关系最后更新时间",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_id(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if "_id" in out and out.get("id") is None:
            out["id"] = str(out.pop("_id"))
        return out

    @classmethod
    def from_mongo(cls, doc: dict[str, Any]) -> Self:
        return cls.model_validate(doc)

    def to_mongo(self) -> dict[str, Any]:
        d = self.model_dump(mode="python", exclude_none=True, exclude={"id"})
        st = d.get("status")
        if isinstance(st, UserJobStatusEnum):
            d["status"] = st.value
        al = d.get("attention_level")
        if isinstance(al, AttentionLevelEnum):
            d["attention_level"] = int(al)
        if self.id is not None:
            d["_id"] = self.id
        return d

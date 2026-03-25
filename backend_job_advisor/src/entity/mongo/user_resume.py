"""Mongo ``user_resume``：与用户 1:1 的简历文档。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from entity.mongo.resume_basic_info import ResumeBasicInfo
from entity.mongo.resume_education import ResumeEducation
from entity.mongo.resume_job_intent import ResumeJobIntent
from entity.mongo.resume_work_experience import ResumeWorkExperience


class UserResume(BaseModel):
    """用户简历全量结构。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str | None = Field(
        default=None,
        description="MongoDB 文档 _id 的字符串形式；读库时由 _id 映射",
    )
    user_id: str = Field(..., description="用户唯一标识，与账号一一对应")
    basic_info: ResumeBasicInfo = Field(
        default_factory=ResumeBasicInfo,
        description="基本信息（年龄、联系方式、性别等）",
    )
    work_experience: list[ResumeWorkExperience] = Field(
        default_factory=list,
        description="工作经历列表，按时间倒序或展示序由业务决定",
    )
    education: list[ResumeEducation] = Field(
        default_factory=list,
        description="教育经历列表",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="技能标签列表",
    )
    job_intent: ResumeJobIntent = Field(
        default_factory=ResumeJobIntent,
        description="求职意向（岗位、城市、薪资、工作方式等）",
    )
    created_at: datetime | None = Field(default=None, description="文档创建时间")
    updated_at: datetime | None = Field(default=None, description="文档最后更新时间")

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
        if self.id is not None:
            d["_id"] = self.id
        return d

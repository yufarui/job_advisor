"""简历（user_resume）部分更新：API 与 Agent 工具共用字段定义。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from entity.mongo.resume_basic_info import ResumeBasicInfo
from entity.mongo.resume_education import ResumeEducation
from entity.mongo.resume_job_intent import ResumeJobIntent
from entity.mongo.resume_work_experience import ResumeWorkExperience


class ResumeUpdateResponse(BaseModel):
    """HTTP 更新成功时的固定响应。"""

    model_config = ConfigDict(extra="ignore")

    ok: Literal[True] = Field(description="恒为 true，表示写入成功")


class ResumeUpdateToolInput(BaseModel):
    """Agent 工具 updateResume 的入参 """

    model_config = ConfigDict(extra="ignore")

    basic_info: ResumeBasicInfo | None = Field(
        default=None,
        description="基本信息片段；仅出现的子字段参与更新",
    )
    work_experience: list[ResumeWorkExperience] | None = Field(
        default=None,
        description="工作经历列表",
    )
    education: list[ResumeEducation] | None = Field(
        default=None,
        description="教育经历列表",
    )
    skills: list[str] | None = Field(default=None, description="技能标签")
    job_intent: ResumeJobIntent | None = Field(
        default=None,
        description="求职意向；远程办公请用 work_mode=\"remote\"，勿用 pref_work_mode",
    )


class ResumeUpdateRequest(BaseModel):
    """HTTP/API 部分更新简历；未传字段表示不改。"""

    model_config = ConfigDict(extra="ignore")

    user_id: str = Field(description="简历所属用户 ID")
    basic_info: ResumeBasicInfo | None = Field(default=None, description="基本信息片段")
    work_experience: list[ResumeWorkExperience] | None = Field(
        default=None,
        description="工作经历列表",
    )
    education: list[ResumeEducation] | None = Field(default=None, description="教育经历列表")
    skills: list[str] | None = Field(default=None, description="技能标签")
    job_intent: ResumeJobIntent | None = Field(default=None, description="求职意向")

    def to_mongo_set(self) -> dict[str, Any]:
        """转为 ``$set`` 字段（不含 ``user_id``）；未传字段不出现。"""
        data = self.model_dump(
            mode="python",
            exclude_unset=True,
            exclude_none=True,
            exclude={"user_id"},
        )
        out: dict[str, Any] = {}
        for k, v in data.items():
            if k in ("basic_info", "job_intent") and hasattr(v, "model_dump"):
                out[k] = v.model_dump(mode="python", exclude_none=True)
            elif k in ("work_experience", "education") and isinstance(v, list):
                out[k] = [
                    item.model_dump(mode="python", exclude_none=True)
                    if hasattr(item, "model_dump")
                    else item
                    for item in v
                ]
            elif isinstance(v, Enum):
                out[k] = v.value
            else:
                out[k] = v
        return out

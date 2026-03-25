"""简历上传：结构化字段 + 可选 PDF。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from entity.mongo.resume_basic_info import ResumeBasicInfo
from entity.mongo.resume_education import ResumeEducation
from entity.mongo.resume_job_intent import ResumeJobIntent
from entity.mongo.resume_work_experience import ResumeWorkExperience


class ResumeUploadRequest(BaseModel):
    """新建或覆盖式写入简历时的请求体。"""

    model_config = ConfigDict(extra="ignore")

    user_id: str = Field(description="简历所属用户 ID")
    basic_info: ResumeBasicInfo | None = Field(default=None, description="基本信息")
    work_experience: list[ResumeWorkExperience] | None = Field(
        default=None,
        description="工作经历",
    )
    education: list[ResumeEducation] | None = Field(default=None, description="教育经历")
    skills: list[str] | None = Field(default=None, description="技能标签")
    job_intent: ResumeJobIntent | None = Field(default=None, description="求职意向")
    pdf: str | None = Field(
        default=None,
        description="PDF：Base64 或已上传文件 URL，由后端处理",
    )

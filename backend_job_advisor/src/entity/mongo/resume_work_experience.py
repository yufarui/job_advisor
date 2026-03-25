"""简历嵌套对象：一条工作经历。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ResumeWorkExperience(BaseModel):
    """user_resume.work_experience 数组元素。"""

    model_config = ConfigDict(extra="ignore")

    company: str | None = Field(default=None, description="公司名称")
    title: str | None = Field(default=None, description="职位名称")
    start_date: str | None = Field(
        default=None,
        description="入职时间，建议格式如 2020-01",
    )
    end_date: str | None = Field(
        default=None,
        description="离职时间，建议格式如 2024-06；在职可写「至今」等约定文案",
    )
    description: str | None = Field(default=None, description="工作内容与业绩描述")
    created_at: datetime | None = Field(
        default=None,
        description="本条记录创建时间（服务端写入）",
    )

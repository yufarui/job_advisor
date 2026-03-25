"""简历嵌套对象：一条教育经历。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResumeEducation(BaseModel):
    """user_resume.education 数组元素。"""

    model_config = ConfigDict(extra="ignore")

    school: str | None = Field(default=None, description="学校名称")
    degree: str | None = Field(default=None, description="学历或学位（如本科、硕士）")
    major: str | None = Field(default=None, description="专业")
    start_date: str | None = Field(default=None, description="入学时间，建议 YYYY-MM")
    end_date: str | None = Field(default=None, description="毕业时间，建议 YYYY-MM")

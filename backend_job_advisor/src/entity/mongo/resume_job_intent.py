"""简历嵌套对象：求职意向（岗位、城市、薪资、工作方式）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResumeJobIntent(BaseModel):
    """嵌套于 user_resume.job_intent。"""

    model_config = ConfigDict(extra="ignore")

    roles: list[str] = Field(
        default_factory=list,
        description="期望岗位名称列表（可多选）",
    )
    cities: list[str] = Field(
        default_factory=list,
        description="期望工作城市列表",
    )
    salary_expectation: str | None = Field(
        default=None,
        description="期望薪资范围或说明（自由文本）",
    )
    work_mode: str | None = Field(
        default=None,
        description="工作方式：remote（远程）/ hybrid（混合）/ onsite（现场）；勿使用 pref_work_mode 等别名",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_work_mode_aliases(cls, data: Any) -> Any:
        """LLM 常误写 pref_work_mode；在校验前合并到 work_mode。"""
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if "pref_work_mode" in d:
            alias_val = d.pop("pref_work_mode")
            if d.get("work_mode") in (None, "") and alias_val not in (None, ""):
                d["work_mode"] = alias_val
        return d

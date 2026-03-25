"""Mongo ``jobs`` 集合：职位主数据（biz_id 为业务主键）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from constants.job_source_enum import JobSourceEnum


class Job(BaseModel):
    """一条职位文档。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str | None = Field(
        default=None,
        description="Mongo _id 转字符串；读库时由 _id 填入",
    )
    biz_id: str = Field(
        ...,
        description="业务侧职位唯一编号，列表与检索主键",
    )
    source: JobSourceEnum = Field(
        default=JobSourceEnum.unknown,
        description="数据来源（枚举 JobSourceEnum）",
    )
    title: str = Field(default="", description="职位名称")
    company: str = Field(default="", description="公司或雇主名称")
    city: str = Field(default="", description="工作城市或地点")
    salary_range: str | None = Field(
        default=None,
        description="薪资范围展示文案（如 20k-35k）",
    )
    jd_text: str = Field(
        default="",
        description="职位描述（JD）正文",
    )
    created_at: datetime | None = Field(default=None, description="职位记录创建时间")
    updated_at: datetime | None = Field(default=None, description="职位记录最后更新时间")

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
        src = d.get("source")
        if isinstance(src, JobSourceEnum):
            d["source"] = src.value
        if self.id is not None:
            d["_id"] = self.id
        return d

"""职位实体（jobs 集合）部分更新。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from constants.job_source_enum import JobSourceEnum


class JobUpdateResponse(BaseModel):
    """HTTP 更新成功时的固定响应。"""

    model_config = ConfigDict(extra="ignore")

    ok: Literal[True] = Field(description="恒为 true，表示写入成功")


class JobUpdateRequest(BaseModel):
    """按 biz_id 定位职位；未传字段表示不改。"""

    model_config = ConfigDict(extra="ignore")

    biz_id: str = Field(description="要更新的职位业务编号")
    title: str | None = Field(default=None, description="职位名称")
    company: str | None = Field(default=None, description="公司名")
    city: str | None = Field(default=None, description="城市或地点")
    salary_range: str | None = Field(default=None, description="薪资展示文案")
    jd_text: str | None = Field(default=None, description="职位描述正文")
    source: JobSourceEnum | None = Field(default=None, description="数据来源（枚举）")

    def to_mongo_set(self) -> dict[str, Any]:
        """转为 ``$set`` 字段（不含 ``biz_id``）；未传字段不出现。"""
        data = self.model_dump(
            mode="python",
            exclude_unset=True,
            exclude_none=True,
            exclude={"biz_id"},
        )
        out: dict[str, Any] = {}
        for k, v in data.items():
            out[k] = v.value if isinstance(v, Enum) else v
        return out

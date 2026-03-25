"""Mongo ``tasks``：对话主任务（与用户输入会话绑定）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Task(BaseModel):
    """一条主任务文档。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str | None = Field(
        default=None,
        description="Mongo _id 转字符串；读库时由 _id 填入",
    )
    user_id: str = Field(..., description="所属用户 ID")
    user_input: str = Field(
        default="",
        description="用户触发或概括该主任务的原始输入摘要",
    )
    status: Literal["active", "closed", "archived"] = Field(
        default="active",
        description="主任务生命周期：active 进行中 / closed 已结束 / archived 已归档",
    )
    created_at: datetime | None = Field(default=None, description="主任务创建时间")
    updated_at: datetime | None = Field(default=None, description="主任务最后更新时间")

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

"""Mongo ``sub_tasks``：主任务下的子任务（工具调用、澄清、事实确认等）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from constants.sub_task_status_enum import SubTaskStatusEnum
from constants.sub_task_type_enum import SubTaskTypeEnum


class SubTask(BaseModel):
    """一条子任务文档。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str | None = Field(
        default=None,
        description="Mongo _id 转字符串；读库时由 _id 填入",
    )
    task_id: str = Field(..., description="所属主任务 ID（tasks._id）")
    task_type: SubTaskTypeEnum = Field(
        ...,
        description="类型（枚举 SubTaskTypeEnum）",
    )
    status: SubTaskStatusEnum = Field(
        default=SubTaskStatusEnum.created,
        description="状态（枚举 SubTaskStatusEnum）",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="工具调用参数或槽位填充结果（JSON 可序列化字典）",
    )
    tool_name: str | None = Field(
        default=None,
        description="若已绑定工具，则为 LangChain 工具名",
    )
    result_cache_key: str | None = Field(
        default=None,
        description="工具结果缓存键（若有）",
    )
    error_message: str | None = Field(
        default=None,
        description="失败时的错误信息",
    )
    created_at: datetime | None = Field(default=None, description="子任务创建时间")
    updated_at: datetime | None = Field(default=None, description="子任务最后更新时间")

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

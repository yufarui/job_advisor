"""用户—职位关系（user_jobs）的更新请求与工具入参。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from constants.attention_level_enum import AttentionLevelEnum
from constants.user_job_status_enum import UserJobStatusEnum


class UserJobUpdateResponse(BaseModel):
    """HTTP 更新成功时的固定响应。"""

    model_config = ConfigDict(extra="ignore")

    ok: Literal[True] = Field(description="恒为 true，表示写入成功")


class UserJobUpdateToolInput(BaseModel):
    """Agent 工具 updateJobs 的入参（不含 user_id，由会话注入）。"""

    model_config = ConfigDict(extra="ignore")

    biz_id: str = Field(
        ...,
        min_length=1,
        description="职位业务编号，对应 jobs.biz_id 与 user_jobs.job_id",
    )
    status: UserJobStatusEnum | None = Field(
        default=None,
        description="用户侧职位状态（枚举）",
    )
    attention_level: AttentionLevelEnum | None = Field(
        default=None,
        description="关注程度（枚举，1–5）",
    )
    note: str | None = Field(default=None, description="用户备注")


class UserJobUpdateRequest(BaseModel):
    """HTTP/API 更新 user_jobs 的请求体；未传字段表示不改。"""

    model_config = ConfigDict(extra="ignore")

    user_id: str = Field(description="用户 ID")
    biz_id: str = Field(description="职位业务编号，对应 jobs.biz_id")
    status: UserJobStatusEnum | None = Field(default=None, description="用户侧职位状态（枚举）")
    attention_level: AttentionLevelEnum | None = Field(
        default=None,
        description="关注程度（枚举）",
    )
    note: str | None = Field(default=None, description="用户备注")

    def to_mongo_set(self) -> dict[str, Any]:
        """转为 ``$set`` 字段（不含 ``user_id`` / ``job_id`` 定位键）。"""
        data = self.model_dump(
            mode="python",
            exclude_unset=True,
            exclude_none=True,
            exclude={"user_id", "biz_id"},
        )
        out: dict[str, Any] = {}
        for k, v in data.items():
            if k == "attention_level" and isinstance(v, Enum):
                out[k] = int(v)
            elif isinstance(v, Enum):
                out[k] = v.value
            else:
                out[k] = v
        return out

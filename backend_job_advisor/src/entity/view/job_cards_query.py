"""职位卡片列表的查询参数（GET query）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from constants.user_job_status_enum import UserJobStatusEnum


class JobCardsQuery(BaseModel):
    """按用户与可选条件筛选职位卡片。"""

    model_config = ConfigDict(extra="ignore")

    user_id: str = Field(description="用户 ID")
    status: UserJobStatusEnum | None = Field(
        default=None,
        description="用户侧职位状态（枚举）；空表示不限",
    )
    created_from: datetime | None = Field(
        default=None,
        description="职位创建时间下限（含）",
    )
    created_to: datetime | None = Field(
        default=None,
        description="职位创建时间上限（含）",
    )

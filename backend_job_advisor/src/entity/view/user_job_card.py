"""职位卡片：列表页单行展示用摘要。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from constants.attention_level_enum import AttentionLevelEnum
from constants.user_job_status_enum import UserJobStatusEnum


class UserJobCard(BaseModel):
    """合并职位与用户关系后的卡片数据。"""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(description="职位名称")
    biz_id: str = Field(description="职位业务编号")
    description: str = Field(description="JD 摘要或全文，前端可截断")
    status: UserJobStatusEnum = Field(description="用户侧状态（枚举）")
    attention_level: AttentionLevelEnum | None = Field(
        default=None,
        description="关注度（枚举）",
    )
    salary: str | None = Field(default=None, description="薪资文案，对应 salary_range")


class UserJobCardListResponse(BaseModel):
    """卡片列表 API 响应。"""

    model_config = ConfigDict(extra="ignore")

    cards: list[UserJobCard] = Field(default_factory=list, description="卡片数组")

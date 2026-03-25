"""单条用户事实的 PATCH 请求。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from constants.fact_predicate_enum import FactPredicateEnum
from constants.fact_status_enum import FactStatusEnum


class FactUpdateResponse(BaseModel):
    """更新成功固定响应。"""

    model_config = ConfigDict(extra="ignore")

    ok: Literal[True] = Field(description="恒为 true")


class UserFactUpdateRequest(BaseModel):
    """按 fact_no 更新；未传字段不改。"""

    model_config = ConfigDict(extra="ignore", use_enum_values=True)

    fact_no: str = Field(description="事实主键，与 ES _id / Chroma id 相同")
    user_id: str = Field(description="所属用户 ID")
    predicate: FactPredicateEnum | None = Field(default=None, description="谓词（枚举）")
    value: str | None = Field(default=None, description="结构化取值")
    content: str | None = Field(default=None, description="自然语言表述")
    status: FactStatusEnum | None = Field(default=None, description="状态（枚举）")
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="置信度 0–1",
    )
    entities: dict[str, list[str]] | None = Field(
        default=None,
        description="实体槽，如公司名列表",
    )

    def to_elasticsearch_partial(self) -> dict[str, Any]:
        return self.model_dump(
            mode="python",
            exclude_unset=True,
            exclude_none=True,
            exclude={"fact_no", "user_id"},
        )

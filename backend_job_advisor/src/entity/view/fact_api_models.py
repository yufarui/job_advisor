"""事实模块：批量写入、检索、后端管道 upsert 的请求与响应。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from entity.domain.fact_domain import Fact
from entity.view.user_fact_view import UserFactView


class FactBulkInsertRequest(BaseModel):
    """页面批量新增事实。"""

    model_config = ConfigDict(extra="ignore")

    facts: list[Fact] = Field(
        default_factory=list,
        description="待插入事实；新建时 fact_no 为空，由服务端生成",
    )


class FactBulkInsertResponse(BaseModel):
    """批量插入返回。"""

    model_config = ConfigDict(extra="ignore")

    inserted_fact_nos: list[str] = Field(
        default_factory=list,
        description="新事实编号列表",
    )
    count: int = Field(ge=0, description="成功条数")


class FactPageBulkAddResult(BaseModel):
    """页面批量新增的业务结果（失败时看 reason / duplicates）。"""

    model_config = ConfigDict(extra="ignore")

    ok: bool = Field(description="是否全部成功")
    reason: str | None = Field(
        default=None,
        description="失败原因码，如 duplicate_predicate",
    )
    duplicates: list[UserFactView] = Field(
        default_factory=list,
        description="与已有事实冲突的条目",
    )
    inserted_fact_nos: list[str] = Field(
        default_factory=list,
        description="成功写入的 fact_no",
    )


class UserFactListResponse(BaseModel):
    """用户事实列表。"""

    model_config = ConfigDict(extra="ignore")

    facts: list[UserFactView] = Field(default_factory=list, description="事实数组")


class FactDialogueSearchRequest(BaseModel):
    """用一句对话检索相关事实（ES + 向量合并）。"""

    model_config = ConfigDict(extra="ignore")

    dialogue: str = Field(min_length=1, description="用户一句话")
    es_limit: int = Field(default=20, ge=1, le=50, description="ES 最多返回条数")
    chroma_limit: int = Field(
        default=20,
        ge=1,
        le=50,
        description="向量库最多返回条数",
    )
    merge_limit: int = Field(
        default=40,
        ge=1,
        le=100,
        description="合并去重后上限",
    )


class BackendFactUpsertRequest(BaseModel):
    """Agent/管道写入事实：新增或按 fact_no 更新。"""

    model_config = ConfigDict(extra="ignore")

    facts: list[Fact] = Field(default_factory=list, description="事实列表")
    ignore_duplicate: bool = Field(
        default=False,
        description="为 true 时不做重复检测，直接写库",
    )


class BackendFactUpsertResponse(BaseModel):
    """管道 upsert 结果。"""

    model_config = ConfigDict(extra="ignore")

    success: bool = Field(description="是否整体成功")
    duplicate_facts: list[UserFactView] = Field(
        default_factory=list,
        description="被判重复的已有事实",
    )
    inserted_fact_nos: list[str] = Field(
        default_factory=list,
        description="新建 fact_no",
    )
    updated_fact_nos: list[str] = Field(
        default_factory=list,
        description="更新 fact_no",
    )
    errors: list[str] = Field(default_factory=list, description="错误信息列表")

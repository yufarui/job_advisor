"""用户事实领域模型：与 ES、向量库存储字段对齐。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from constants.fact_predicate_enum import FactPredicateEnum
from constants.fact_status_enum import FactStatusEnum


class Fact(BaseModel):
    """一条用户事实；fact_no 与 ES _id、Chroma id 一致。"""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        frozen=False,
        use_enum_values=True,
    )

    fact_no: str | None = Field(
        default=None,
        description="业务主键；新建可空，服务端可按 user_id+predicate 生成",
    )
    user_id: str = Field(description="所属用户 ID")
    predicate: FactPredicateEnum = Field(description="谓词（枚举）")
    value: str = Field(default="", description="结构化取值")
    content: str = Field(default="", description="自然语言内容")
    entities: dict[str, list[str]] = Field(
        default_factory=dict,
        description="附加实体，如提及的公司名",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度 0–1")
    status: FactStatusEnum = Field(default=FactStatusEnum.ACTIVE, description="状态（枚举）")
    created_at: datetime | None = Field(default=None, description="创建时间")

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_keys(cls, data: Any) -> Any:
        """ES 命中可把 _id 填回 fact_no。"""
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if "_id" in out and out.get("fact_no") in (None, ""):
            out["fact_no"] = str(out.pop("_id"))
        return out

    @model_validator(mode="after")
    def validate_content(self) -> Fact:
        if not (self.content or self.value):
            raise ValueError("Fact.content or Fact.value 至少一个非空")
        if not (self.fact_no and str(self.fact_no).strip()):
            self.fact_no = self.generate_fact_no(self.user_id, self.predicate)
        return self

    @staticmethod
    def generate_fact_no(user_id: str, predicate: FactPredicateEnum | str) -> str:
        uid = (user_id or "").strip()
        pred = str(predicate).strip()
        if not uid or not pred:
            raise ValueError("generate_fact_no requires non-empty user_id and predicate")
        return f"user_{uid}:{pred}"

    def to_es_doc(self) -> dict[str, Any]:
        """写入 ES 的正文字段。"""
        return self.model_dump(
            mode="json",
            exclude_none=True,
        )

    @classmethod
    def from_es_hit(cls, hit: dict[str, Any]) -> Fact:
        src = dict(hit.get("_source") or {})
        fid = str(hit.get("_id") or "")
        if not src.get("fact_no") and fid:
            src["fact_no"] = fid
        return cls.model_validate(src)

    def to_chroma_id(self) -> str:
        if not self.fact_no or not str(self.fact_no).strip():
            raise ValueError("Fact.fact_no is required for Chroma")
        return str(self.fact_no).strip()

    def to_chroma_metadata(self) -> dict[str, str | int | float]:
        meta: dict[str, str | int | float] = {
            "user_id": self.user_id,
            "predicate": str(self.predicate),
            "status": str(self.status),
            "fact_no": self.fact_no or "",
            "confidence": float(self.confidence),
        }
        if self.entities:
            meta["entities_json"] = json.dumps(
                self.entities,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        return meta

    def to_chroma_document(self) -> str:
        return self.content or self.value

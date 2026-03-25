"""Redis 中短期对话的单条消息（List 元素 JSON）。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field


class DialogueMessage(BaseModel):
    """一条对话轮次，序列化后存入 Redis List。"""

    model_config = ConfigDict(extra="ignore")

    role: Literal["user", "assistant", "system"] = Field(
        default="user",
        description="发言角色",
    )
    content: str = Field(default="", description="消息正文")
    ts: datetime | None = Field(default=None, description="服务端时间戳，可选")

    def to_redis_element(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_redis_element(cls, raw: str | bytes) -> Self:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return cls.model_validate_json(raw)

    @classmethod
    def load_many_from_list(cls, elements: list[str | bytes]) -> list[Self]:
        return [cls.from_redis_element(x) for x in elements]

    @staticmethod
    def dump_many_to_jsonl(messages: list[DialogueMessage]) -> str:
        return "\n".join(m.model_dump_json() for m in messages)

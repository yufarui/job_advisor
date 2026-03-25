"""单次用户输入在各 Agent 阶段之间传递的可变状态（便于后续接入 LangGraph reducers）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from entity.redis.dialogue_message import DialogueMessage


class AdvisorTurnState(BaseModel):
    """一轮对话在 Triage → Plan → Review → Executor 中的共享状态。"""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    user_id: str
    user_input: str

    task_id: str | None = Field(
        default=None, description="当前绑定主任务 id（Mongo tasks）"
    )
    task_is_new: bool = Field(default=False, description="本轮是否新建主任务")

    history_dialogue: list[DialogueMessage] = Field(
        default_factory=list, description="历史对话记录"
    )

    # Plan：进入 LLM / 上下文的结构化事实摘要（JSON 字符串，避免与图状态深度耦合）
    facts_context_json: str = Field(
        default="",
        description="混合检索事实序列化结果，供 Plan / Executor 注入提示词",
    )

    planned_sub_tasks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Plan 输出的子任务（tool_call / tool_slot_clarify / fact_confirm），供 Executor / Review",
    )
    plan_user_notices: list[str] = Field(
        default_factory=list,
        description="需显式提示用户：同参重复、事实冲突等（设计文档 Plan 细则）",
    )

    # Executor 产出
    assistant_reply: str | None = Field(
        default=None, description="面向用户的自然语言回复"
    )

    # 非致命告警（如某阶段降级）
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    # Pipeline 内部标记：避免同一轮重复写 Redis 对话
    dialogue_user_persisted: bool = Field(default=False)
    dialogue_assistant_persisted: bool = Field(default=False)

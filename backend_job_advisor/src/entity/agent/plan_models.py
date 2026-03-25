"""Plan 阶段结构化输出：子任务项（工具槽位 / 澄清 / 事实确认 / 纯对话）。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, BeforeValidator, Field, WithJsonSchema

from constants.fact_predicate_enum import FactPredicateEnum
from constants.sub_task_status_enum import SubTaskStatusEnum
from constants.sub_task_type_enum import SubTaskTypeEnum
from entity.mongo.sub_task import SubTask
from pydantic.networks import AnyHttpUrl


def _normalize_json_string_values(v: Any) -> Any:
    """将形如 JSON 对象/数组的字符串值递归转为原生类型。"""
    if isinstance(v, str):
        s = v.strip()
        if not s or s[0] not in "{[":
            return v
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            return v
        if isinstance(parsed, (dict, list)):
            return _normalize_json_string_values(parsed)
        return v
    if isinstance(v, Mapping):
        return {str(k): _normalize_json_string_values(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_normalize_json_string_values(x) for x in v]
    return v


def _coerce_tool_args_dict(v: Any) -> dict[str, Any]:
    """统一为 dict[str, Any]，并兜底反序列化被误包成 jsonstr 的对象/数组字段。"""
    if v is None:
        return {}
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return {}
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError as e:
            raise ValueError(f"tool params must be valid JSON object: {e}") from e
        if not isinstance(parsed, dict):
            raise ValueError("tool params JSON must be a JSON object")
        return _normalize_json_string_values(parsed)
    if isinstance(v, Mapping):
        return _normalize_json_string_values(v)
    raise ValueError(f"tool params must be a mapping or JSON object string, got {type(v).__name__}")


# BeforeValidator：在 core 校验 ``dict`` 之前执行，兼容整段 JSON 字符串。
# WithJsonSchema(anyOf)：schema 允许 object（任意属性类型）或 string，与 dict[str, Any] 一致。
ToolParamsDict = Annotated[
    dict[str, Any],
    BeforeValidator(_coerce_tool_args_dict),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "object", "additionalProperties": True},
                {"type": "string"},
            ],
        }
    ),
]


class PlanItemSlot(BaseModel):
    """执行一次工具调用。"""

    kind: Literal["slot"] = Field(description="固定为 slot")
    tool_name: str = Field(description="工具名，须与注册名一致")
    tool_params: ToolParamsDict = Field(
        description="参数名到值的映射（使用原生 JSON 类型）；禁止把对象/数组序列化成 JSON 字符串",
    )

    def to_sub_task(self, task_id: str) -> SubTask:
        return SubTask(
            task_id=task_id,
            task_type=SubTaskTypeEnum.tool_call,
            status=SubTaskStatusEnum.created,
            params=dict(self.tool_params),
            tool_name=(self.tool_name or "").strip() or None,
        )


class PlanItemClarify(BaseModel):
    """对挂起子任务补充槽位。"""

    kind: Literal["clarify"] = Field(description="固定为 clarify")
    bind_task_id: str = Field(description="待澄清子任务的 Mongo _id")
    tool_name: str = Field(description="关联工具名")
    supplement_params: ToolParamsDict = Field(
        description="待合并的补充参数（键到原生 JSON 类型值）；禁止把对象/数组序列化成 JSON 字符串",
    )

    def to_sub_task(self, task_id: str) -> SubTask:
        return SubTask(
            task_id=task_id,
            task_type=SubTaskTypeEnum.tool_slot_clarify,
            status=SubTaskStatusEnum.created,
            params={
                "bind_task_id": (self.bind_task_id or "").strip(),
                "supplement_params": dict(self.supplement_params),
            },
            tool_name=(self.tool_name or "").strip() or None,
        )


class PlanItemFactConfirm(BaseModel):
    """事实冲突，需用户确认新旧内容。"""

    kind: Literal["fact_confirm"] = Field(description="固定为 fact_confirm")
    bind_task_id: str | None = Field(
        default=None,
        description="要更新的既有 fact_confirm 子任务 id；新建时可为空",
    )
    confirm_state: Literal["created", "agree", "disagree"] = Field(
        default="created",
        description="确认状态：created=待确认，agree=用户同意更新，disagree=用户不同意",
    )
    current_fact_content: str = Field(description="当前已存事实文案")
    new_fact_content: str = Field(description="拟写入的新文案")
    predicate: FactPredicateEnum = Field(description="谓词（枚举）")
    value: str = Field(description="事实 value 字段")

    def to_sub_task(self, task_id: str) -> SubTask:
        return SubTask(
            task_id=task_id,
            task_type=SubTaskTypeEnum.fact_confirm,
            status=SubTaskStatusEnum.created,
            params={
                "bind_task_id": (self.bind_task_id or "").strip(),
                "confirm_state": self.confirm_state,
                "predicate": self.predicate.value,
                "value": self.value,
                "current_fact_content": self.current_fact_content,
                "new_fact_content": self.new_fact_content,
            },
            tool_name=None,
        )


class PlanItemChat(BaseModel):
    """无需工具，直接对话回复。"""

    kind: Literal["chat"] = Field(description="固定为 chat")

    def to_sub_task(self, task_id: str) -> SubTask:
        return SubTask(
            task_id=task_id,
            task_type=SubTaskTypeEnum.chat,
            status=SubTaskStatusEnum.created,
            tool_name=None,
        )


PlanAdvisorItem = Annotated[
    Union[PlanItemSlot, PlanItemClarify, PlanItemFactConfirm, PlanItemChat],
    Field(discriminator="kind"),
]


class PlanAdvisorTurnResult(BaseModel):
    """本轮 Plan 的输出；items 可混合多种 kind。"""

    items: list[PlanAdvisorItem] = Field(
        description="按优先级排列的子任务项列表",
    )

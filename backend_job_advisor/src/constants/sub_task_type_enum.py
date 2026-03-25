from enum import Enum


class SubTaskTypeEnum(str, Enum):
    tool_call = "tool_call"
    tool_slot_clarify = "tool_slot_clarify"
    fact_confirm = "fact_confirm"
    chat = "chat"

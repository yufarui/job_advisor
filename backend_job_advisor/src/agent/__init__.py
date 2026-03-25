"""求职顾问 Agent 阶段实现（设计文档 §9）：Triage / Plan / Review / Executor。"""

from __future__ import annotations

from constants.agent_constants import AgentConstants
from importlib import import_module
from typing import Any

__all__ = [
    "AgentConstants",
    "AdvisorTurnState",
    "SubTaskPort",
    "SubTaskReadPort",
    "TaskLifecyclePort",
    "ToolResultCachePort",
    "run_executor",
    "run_plan",
    "run_review",
    "run_triage",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "AdvisorTurnState": ("agent.state", "AdvisorTurnState"),
    "SubTaskPort": ("agent.ports", "SubTaskPort"),
    "SubTaskReadPort": ("agent.ports", "SubTaskReadPort"),
    "TaskLifecyclePort": ("agent.ports", "TaskLifecyclePort"),
    "ToolResultCachePort": ("agent.ports", "ToolResultCachePort"),
    "run_executor": ("agent.executor", "run_executor"),
    "run_plan": ("agent.plan", "run_plan"),
    "run_review": ("agent.review", "run_review"),
    "run_triage": ("agent.triage", "run_triage"),
}


def __getattr__(name: str) -> Any:
    if name == "AgentConstants":
        return AgentConstants
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'agent' has no attribute '{name}'")
    module_path, symbol = target
    module = import_module(module_path)
    value = getattr(module, symbol)
    globals()[name] = value
    return value

"""LangChain ``@tool`` 形式的求职顾问工具（设计文档 §10）。"""

from __future__ import annotations

from tool.advisor_tools import build_advisor_tools
from tool.context import AdvisorToolContext
from tool.metadata import TOOL_RETURNS_FETCHABLE_PAYLOAD, returns_fetchable_payload

__all__ = [
    "AdvisorToolContext",
    "TOOL_RETURNS_FETCHABLE_PAYLOAD",
    "build_advisor_tools",
    "returns_fetchable_payload",
]

"""设计文档 §10：Review 层用于判断是否写入「可缓存工具结果」的元数据。"""

from __future__ import annotations

from typing import Any
from typing import Final

# 工具名（与 LangChain ``@tool`` 注册名一致） -> 是否返回可供 Executor 缓存拉取的结构化信息
TOOL_RETURNS_FETCHABLE_PAYLOAD: Final[dict[str, bool]] = {
    "searchJobs": True,
    "searchResume": True,
    "searchCompany": True,
    "updateJobs": False,
    "updateResume": False,
    "notifyUser": False,
}


def returns_fetchable_payload(tool_name: str) -> bool:
    return TOOL_RETURNS_FETCHABLE_PAYLOAD.get(tool_name, False)


# 工具名 -> one-of 字段组；每组表示“至少一个字段有值”
TOOL_ONE_OF_REQUIRED_FIELDS: Final[dict[str, tuple[tuple[str, ...], ...]]] = {
    "searchJobs": (("biz_ids", "title"),),
}


def _has_value(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, list):
        return any(_has_value(x) for x in v)
    return True


def extra_missing_fields(tool_name: str, params: dict[str, Any]) -> list[str]:
    """返回工具级补充缺参（非 schema.required）。"""
    groups = TOOL_ONE_OF_REQUIRED_FIELDS.get(tool_name.strip(), ())
    missing: list[str] = []
    for group in groups:
        if not group:
            continue
        if any(_has_value(params.get(field)) for field in group):
            continue
        # 缺一组时，用第一个字段触发现有澄清模板。
        missing.append(group[0])
    return missing

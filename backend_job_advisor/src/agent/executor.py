"""执行（Executor）：Redis 历史 + 事实摘要 + 当前输入 → 回复；事实抽取可异步挂起（设计文档 §9.1）。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.ports import SubTaskPort, ToolResultCachePort
from constants.agent_constants import AgentConstants
from service.llm_service import LlmService
from service.fact_service import FactService
from storage.dialogue_history_storage import DialogueHistoryStorage

from agent.state import AdvisorTurnState

logger = logging.getLogger(__name__)

_SYSTEM_PREFIX = """你是求职顾问助手。根据已知用户事实摘要与近期对话，用简洁中文回复用户。
若事实摘要为空，可正常对话并适度询问求职偏好。"""


async def _build_tool_context(
    *,
    state: AdvisorTurnState,
    sub_task_port: SubTaskPort | None,
    tool_cache: ToolResultCachePort | None,
) -> str:
    if sub_task_port is None or tool_cache is None:
        return "（无）"
    tid = (state.task_id or "").strip()
    if not tid:
        return "（无）"
    rows: list[dict[str, Any]] = []
    try:
        subs = await sub_task_port.list_sub_tasks_by_task(tid)
        for s in subs:
            k = (s.result_cache_key or "").strip()
            if not k:
                continue
            cached = await tool_cache.get(k)
            rows.append(
                {
                    "sub_task_id": s.id,
                    "tool_name": s.tool_name,
                    "status": str(s.status),
                    "result_cache_key": k,
                    "result": cached,
                }
            )
    except Exception as e:
        logger.warning("executor load tool context failed: %s", e)
    if not rows:
        return "（无）"
    return json.dumps(rows, ensure_ascii=False, default=str, indent=2)


async def _extract_facts_async(
    *,
    llm_service: LlmService,
    fact_service: FactService,
    state: AdvisorTurnState,
) -> None:
    text = (state.user_input or "").strip()
    if not text:
        return
    try:
        facts = await llm_service.extract_facts_from_user_input(
            user_id=state.user_id,
            user_input=text,
        )
        if facts:
            await fact_service.upsert_facts_backend(facts, ignore_duplicate=True)
    except Exception as e:
        logger.warning("executor async fact extraction failed: %s", e)


async def run_executor(
    *,
    llm_service: LlmService,
    fact_service: FactService,
    dialogue_storage: DialogueHistoryStorage,
    sub_task_port: SubTaskPort | None,
    tool_cache: ToolResultCachePort | None,
    state: AdvisorTurnState,
) -> None:
    """生成 ``state.assistant_reply``；可选在返回前 ``append`` 用户消息与助手消息到 Redis（由上层决定是否双写）。"""
    if state.errors:
        return
    tid = (state.task_id or "").strip()
    if not tid:
        state.errors.append("executor: 缺少 task_id")
        return

    history_msgs = await dialogue_storage.get_recent(
        state.user_id,
        limit=AgentConstants.DEFAULT_DIALOGUE_HISTORY_LIMIT,
    )
    current_input = (state.user_input or "").strip()
    if history_msgs:
        last = history_msgs[-1]
        # 防御性去重：若历史末条已是本轮 user_input，避免在 Prompt 中重复注入。
        if (
            (last.role or "").strip().lower() == "user"
            and (last.content or "").strip() == current_input
        ):
            history_msgs = history_msgs[:-1]
    lines = [f"{m.role}: {m.content}" for m in history_msgs if m.content]
    history_block = "\n".join(lines[-40:]) if lines else "（暂无历史）"

    facts_block = state.facts_context_json or "（暂无结构化事实）"
    try:
        facts_pretty = json.dumps(json.loads(facts_block), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        facts_pretty = facts_block

    tools_block = await _build_tool_context(
        state=state,
        sub_task_port=sub_task_port,
        tool_cache=tool_cache,
    )

    plan_block = (
        json.dumps(state.planned_sub_tasks, ensure_ascii=False, indent=2)
        if state.planned_sub_tasks
        else "（本轮无新增子任务规划）"
    )

    messages = [
        SystemMessage(
            content=_SYSTEM_PREFIX
            + "\n\n【混合检索事实】\n"
            + facts_pretty
            + "\n\n【本轮规划的子任务】\n"
            + plan_block
            + "\n\n【工具执行结果（缓存）】\n"
            + tools_block
            + "\n\n【近期对话】\n"
            + history_block
        ),
        HumanMessage(content=current_input),
    ]

    # 在大模型回复阶段并行触发事实抽取（不阻塞主回复链路）。
    asyncio.create_task(
        _extract_facts_async(
            llm_service=llm_service,
            fact_service=fact_service,
            state=state,
        )
    )

    try:
        out = await llm_service.chat_model.ainvoke(messages)
        text = getattr(out, "content", None) or str(out)
        state.assistant_reply = text if isinstance(text, str) else str(text)
        logger.info(
            "executor reply_len=%s user_id=%s task_id=%s",
            len(state.assistant_reply or ""),
            state.user_id,
            tid,
        )
    except Exception as e:
        logger.exception("executor llm failed")
        state.errors.append(f"executor: {e}")

"""规划（Plan）：混合检索事实 → LLM 解析意图 → 持久化 ``sub_tasks``（设计文档 §9.1）。"""

from __future__ import annotations

import json
import logging
from typing import Any

from config.notify_sse_hub import NotifySseHub
from constants.agent_constants import AgentConstants
from constants.sub_task_status_enum import SubTaskStatusEnum
from constants.sub_task_type_enum import SubTaskTypeEnum
from entity.agent.plan_models import (
    PlanAdvisorTurnResult,
    PlanItemChat,
    PlanItemClarify,
    PlanItemFactConfirm,
    PlanItemSlot,
)
from entity.mongo.sub_task import SubTask
from service.fact_service import FactService
from service.llm_service import LlmService
from storage.dialogue_history_storage import DialogueHistoryStorage
from storage.job_storage import JobStorage
from storage.resume_storage import ResumeStorage
from tool.advisor_tools import build_advisor_tools, build_tools_spec_for_plan
from tool.context import AdvisorToolContext

from agent.ports import SubTaskPort
from agent.state import AdvisorTurnState

logger = logging.getLogger(__name__)
_UPDATE_TOOLS = {"updateResume", "updateJobs"}


def _require_task_id(state: AdvisorTurnState) -> str | None:
    tid = (state.task_id or "").strip()
    if not tid:
        state.errors.append("plan: 缺少 task_id")
        return None
    return tid


async def _sync_history_dialogue(
    state: AdvisorTurnState,
    dialogue_storage: DialogueHistoryStorage,
    tid: str,
) -> None:
    if state.history_dialogue:
        return
    try:
        state.history_dialogue = await dialogue_storage.get_recent(
            state.user_id,
            limit=AgentConstants.DEFAULT_DIALOGUE_HISTORY_LIMIT,
        )
    except Exception as e:
        logger.warning("plan load history failed: %s", e)


def _dialogue_text_for_search(state: AdvisorTurnState) -> str:
    lines = [
        f"{m.role}: {m.content}"
        for m in state.history_dialogue[-20:]
        if m.content and str(m.content).strip()
    ]
    base = "\n".join(lines)
    u = (state.user_input or "").strip()
    if u:
        return f"{base}\nuser: {u}" if base else f"user: {u}"
    return base


async def _sync_facts_from_dialogue(
    fact_service: FactService,
    state: AdvisorTurnState,
    dialogue_text: str,
) -> None:
    try:
        views = await fact_service.search_facts_by_dialogue(
            state.user_id,
            dialogue_text,
            es_limit=AgentConstants.DEFAULT_FACT_ES_LIMIT,
            chroma_limit=AgentConstants.DEFAULT_FACT_CHROMA_LIMIT,
            merge_limit=AgentConstants.DEFAULT_FACT_MERGE_LIMIT,
        )
        state.facts_context_json = json.dumps(
            [f.model_dump(mode="json") for f in views],
            ensure_ascii=False,
        )
    except Exception as e:
        logger.exception("plan search_facts_by_dialogue failed")
        state.warnings.append(f"plan: 事实检索失败，继续规划: {e}")
        state.facts_context_json = "[]"


def _advisor_tools_spec(
    job_storage: JobStorage,
    resume_storage: ResumeStorage,
    notify_sse_hub: NotifySseHub,
    state: AdvisorTurnState,
) -> tuple[set[str], list[dict[str, Any]]]:
    ctx = AdvisorToolContext(
        user_id=state.user_id.strip(),
        job_storage=job_storage,
        resume_storage=resume_storage,
        notify_sse_hub=notify_sse_hub,
    )
    tools = build_advisor_tools(ctx)
    return {t.name for t in tools}, build_tools_spec_for_plan(tools)


async def _fetch_open_sub_tasks(
    port: SubTaskPort | None,
    tid: str,
    state: AdvisorTurnState,
) -> list[SubTask]:
    if port is None:
        return []
    try:
        tasks = await port.list_open_sub_tasks(tid)
        return [x for x in tasks if x.task_type != SubTaskTypeEnum.chat]
    except Exception as e:
        logger.warning("plan list_open_sub_tasks failed: %s", e)
        state.warnings.append(f"plan: 未完成任务列表读取失败: {e}")
        return []


def _open_tasks_json(open_tasks: list[SubTask]) -> str:
    rows = [
        {
            "id": s.id,
            "task_type": s.task_type,
            "status": s.status,
            "tool_name": s.tool_name,
            "params": s.params,
        }
        for s in open_tasks
    ]
    return json.dumps(rows, ensure_ascii=False, default=str)


def _history_block(state: AdvisorTurnState) -> str:
    lines = [
        f"{m.role}: {m.content}"
        for m in state.history_dialogue[-24:]
        if m.content and str(m.content).strip()
    ]
    return "\n".join(lines) if lines else "（无）"


async def _invoke_plan_llm(
    llm_service: LlmService,
    state: AdvisorTurnState,
    tools_spec: list[dict[str, Any]],
    open_tasks: list[SubTask],
) -> PlanAdvisorTurnResult | None:
    try:
        return await llm_service.plan_advisor_subtasks(
            user_input=state.user_input,
            history_block=_history_block(state),
            facts_block=state.facts_context_json,
            tools_spec=tools_spec,
            open_sub_tasks_block=_open_tasks_json(open_tasks),
        )
    except Exception as e:
        logger.exception("plan LLM failed")
        state.warnings.append(f"plan: LLM 规划失败: {e}")
        return None


def _plan_items_as_memory_dicts(
    plan_out: PlanAdvisorTurnResult,
    task_id: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in plan_out.items:
        if isinstance(it, (PlanItemClarify, PlanItemFactConfirm, PlanItemChat)):
            out.append(it.to_sub_task(task_id=task_id).model_dump(mode="json"))
            continue
        if not isinstance(it, PlanItemSlot):
            continue
        row = it.to_sub_task(task_id=task_id)
        out.append(row.model_dump(mode="json"))
        notify_params = _build_update_notify_params(
            tool_name=str(row.tool_name or ""),
            params=dict(row.params or {}),
        )
        if not notify_params:
            continue
        out.append(
            SubTask(
                task_id=task_id,
                task_type=SubTaskTypeEnum.tool_call,
                status=SubTaskStatusEnum.created,
                tool_name="notifyUser",
                params=notify_params,
            ).model_dump(mode="json")
        )
    return out


def _build_update_notify_params(
    *,
    tool_name: str,
    params: dict[str, Any],
) -> dict[str, Any] | None:
    name = tool_name.strip()
    if name not in _UPDATE_TOOLS:
        return None
    if name == "updateResume":
        message = "简历修改已经成功。"
    else:
        biz_id = str(params.get("biz_id") or "").strip()
        message = (
            f"职位 {biz_id} 的求职记录修改已经成功。"
            if biz_id
            else "求职记录修改已经成功。"
        )
    return {
        "message": message,
        "severity": "success",
        "event_type": "toast",
    }


def _find_clarify_for_bind(
    open_tasks: list[SubTask],
    bind_task_id: str,
) -> SubTask | None:
    b = bind_task_id.strip()
    if not b:
        return None
    for s in open_tasks:
        if s.task_type != SubTaskTypeEnum.tool_slot_clarify:
            continue
        if str(s.params.get("bind_task_id") or "").strip() == b:
            return s
    return None


def _find_latest_clarify_for_tool(
    open_tasks: list[SubTask],
    tool_name: str,
) -> SubTask | None:
    name = tool_name.strip()
    if not name:
        return None
    # open_tasks 按 created_at 升序；倒序优先匹配最近创建的澄清任务。
    for s in reversed(open_tasks):
        if s.task_type != SubTaskTypeEnum.tool_slot_clarify:
            continue
        if (s.tool_name or "").strip() != name:
            continue
        bind = str((s.params or {}).get("bind_task_id") or "").strip()
        if not bind:
            continue
        return s
    return None


def _find_fact_confirm_for_bind(
    open_tasks: list[SubTask],
    bind_task_id: str,
) -> SubTask | None:
    b = bind_task_id.strip()
    if not b:
        return None
    for s in open_tasks:
        if s.task_type != SubTaskTypeEnum.fact_confirm:
            continue
        if (s.id or "").strip() == b:
            return s
    return None


async def _mark_bound_waiting(
    port: SubTaskPort,
    tid: str,
    state: AdvisorTurnState,
    bind_id: str,
) -> None:
    bound = await port.get_sub_task(tid, bind_id)
    if bound is None:
        state.plan_user_notices.append(f"澄清所绑定的子任务不存在: {bind_id}")
        return
    if bound.task_type == SubTaskTypeEnum.tool_slot_clarify:
        state.plan_user_notices.append("澄清任务不能绑定另一澄清任务")
        return
    if bound.status in (
        SubTaskStatusEnum.success,
        SubTaskStatusEnum.failed,
        SubTaskStatusEnum.cancelled,
    ):
        state.plan_user_notices.append(
            f"绑定的子任务已结束 ({bound.status})，跳过澄清: {bind_id}",
        )
        return
    if not await port.set_sub_task_status(
        tid,
        bind_id,
        SubTaskStatusEnum.waiting.value,
    ):
        state.plan_user_notices.append(f"无法将子任务设为 waiting: {bind_id}")


async def _append_persisted(
    port: SubTaskPort,
    tid: str,
    touched: list[dict[str, Any]],
    sid: str,
) -> None:
    p = await port.get_sub_task(tid, sid)
    if p:
        touched.append(p.model_dump(mode="json"))


async def _persist_plan_items(
    *,
    sub_task_port: SubTaskPort,
    tid: str,
    state: AdvisorTurnState,
    plan_out: PlanAdvisorTurnResult,
    allowed_tool_names: set[str],
    open_tasks: list[SubTask],
) -> list[dict[str, Any]]:
    touched: list[dict[str, Any]] = []

    for it in plan_out.items:
        if isinstance(it, PlanItemSlot):
            name = (it.tool_name or "").strip()
            if name not in allowed_tool_names:
                state.plan_user_notices.append(f"未知工具已忽略: {it.tool_name}")
                continue
            existing_clarify = _find_latest_clarify_for_tool(open_tasks, name)
            if existing_clarify and existing_clarify.id:
                existing_params = dict(existing_clarify.params or {})
                existing_supplement = existing_params.get("supplement_params")
                existing_supplement_dict = (
                    dict(existing_supplement) if isinstance(existing_supplement, dict) else {}
                )
                merged_params = {
                    **existing_params,
                    "supplement_params": {
                        **existing_supplement_dict,
                        **dict(it.tool_params),
                    },
                }
                await sub_task_port.update_sub_task_fields(
                    tid,
                    existing_clarify.id,
                    set_fields={
                        "params": merged_params,
                        "status": SubTaskStatusEnum.waiting.value,
                        "tool_name": name,
                    },
                )
                bind = str(existing_params.get("bind_task_id") or "").strip()
                if bind:
                    await _mark_bound_waiting(sub_task_port, tid, state, bind)
                await _append_persisted(sub_task_port, tid, touched, existing_clarify.id)
                logger.info(
                    "plan slot_routed_to_clarify task_id=%s clarify_id=%s tool=%s",
                    tid,
                    existing_clarify.id,
                    name,
                )
                continue
            row = it.to_sub_task(task_id=tid).model_copy(update={"tool_name": name})
            sid = await sub_task_port.insert_sub_task(row)
            await _append_persisted(sub_task_port, tid, touched, sid)
            notify_params = _build_update_notify_params(
                tool_name=name,
                params=dict(row.params or {}),
            )
            if notify_params:
                if "notifyUser" not in allowed_tool_names:
                    state.warnings.append("plan: notifyUser 不在可用工具中，跳过自动提醒任务")
                    continue
                notify_params = {
                    **notify_params,
                    "_notify_on_success_sub_task_id": sid,
                }
                notify_sid = await sub_task_port.insert_sub_task(
                    SubTask(
                        task_id=tid,
                        task_type=SubTaskTypeEnum.tool_call,
                        status=SubTaskStatusEnum.created,
                        tool_name="notifyUser",
                        params=notify_params,
                    )
                )
                await _append_persisted(sub_task_port, tid, touched, notify_sid)
            continue

        if isinstance(it, PlanItemFactConfirm):
            row = it.to_sub_task(task_id=tid)
            bind = (it.bind_task_id or "").strip()
            existing = _find_fact_confirm_for_bind(open_tasks, bind)
            if existing and existing.id:
                existing_params = dict(existing.params or {})
                incoming_params = dict(row.params or {})
                merged_params = {
                    **existing_params,
                    **incoming_params,
                    "bind_task_id": bind or str(existing_params.get("bind_task_id") or "").strip(),
                }
                await sub_task_port.update_sub_task_fields(
                    tid,
                    existing.id,
                    set_fields={
                        "params": merged_params,
                        "status": SubTaskStatusEnum.waiting.value,
                    },
                )
                await _append_persisted(sub_task_port, tid, touched, existing.id)
                continue
            sid = await sub_task_port.insert_sub_task(row)
            await _append_persisted(sub_task_port, tid, touched, sid)
            continue

        if isinstance(it, PlanItemChat):
            sid = await sub_task_port.insert_sub_task(it.to_sub_task(task_id=tid))
            await _append_persisted(sub_task_port, tid, touched, sid)
            continue

        if not isinstance(it, PlanItemClarify):
            continue

        bind = (it.bind_task_id or "").strip()
        row = it.to_sub_task(task_id=tid)
        new_params = dict(row.params)
        existing = _find_clarify_for_bind(open_tasks, bind)
        if existing and existing.id:
            existing_params = dict(existing.params or {})
            existing_supplement = existing_params.get("supplement_params")
            existing_supplement_dict = (
                dict(existing_supplement) if isinstance(existing_supplement, dict) else {}
            )
            incoming_supplement = new_params.get("supplement_params")
            incoming_supplement_dict = (
                dict(incoming_supplement) if isinstance(incoming_supplement, dict) else {}
            )
            merged_params = {
                **existing_params,
                "bind_task_id": bind or str(existing_params.get("bind_task_id") or "").strip(),
                "supplement_params": {
                    **existing_supplement_dict,
                    **incoming_supplement_dict,
                },
            }
            await sub_task_port.update_sub_task_fields(
                tid,
                existing.id,
                set_fields={
                    "params": merged_params,
                    "status": SubTaskStatusEnum.waiting.value,
                    "tool_name": row.tool_name or existing.tool_name,
                },
            )
            await _mark_bound_waiting(sub_task_port, tid, state, bind)
            await _append_persisted(sub_task_port, tid, touched, existing.id)
            continue

        # 澄清任务由 Review 在 slot 校验缺参时创建；Plan 仅可更新已存在澄清任务。
        if bind:
            await _mark_bound_waiting(sub_task_port, tid, state, bind)
        state.plan_user_notices.append(
            "澄清任务需由 Review 触发创建；本轮 Plan 仅处理已存在澄清。",
        )

    return touched


async def run_plan(
    *,
    fact_service: FactService,
    llm_service: LlmService,
    dialogue_storage: DialogueHistoryStorage,
    job_storage: JobStorage,
    resume_storage: ResumeStorage,
    notify_sse_hub: NotifySseHub,
    state: AdvisorTurnState,
    sub_task_port: SubTaskPort | None = None,
) -> None:
    if state.errors:
        return
    tid = _require_task_id(state)
    if tid is None:
        return
    await _sync_history_dialogue(state, dialogue_storage, tid)
    await _sync_facts_from_dialogue(fact_service, state, _dialogue_text_for_search(state))
    allowed, tools_spec = _advisor_tools_spec(job_storage, resume_storage, notify_sse_hub, state)
    open_tasks = await _fetch_open_sub_tasks(sub_task_port, tid, state)
    plan_out = await _invoke_plan_llm(llm_service, state, tools_spec, open_tasks)
    if plan_out is None:
        state.planned_sub_tasks = []
        return
    if sub_task_port is None:
        state.warnings.append("plan: SubTaskPort 未注入，仅生成内存规划不落库")
        state.planned_sub_tasks = _plan_items_as_memory_dicts(plan_out, tid)
        return
    state.planned_sub_tasks = await _persist_plan_items(
        sub_task_port=sub_task_port,
        tid=tid,
        state=state,
        plan_out=plan_out,
        allowed_tool_names=allowed,
        open_tasks=open_tasks,
    )
    
    logger.info("plan done task_id=%s touched=%s items_in=%s", tid, len(state.planned_sub_tasks), len(plan_out.items))

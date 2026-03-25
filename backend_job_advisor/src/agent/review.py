"""审核（Review）：子任务状态机、工具执行与追问编排（设计文档 §9.1 / §10）。"""

from __future__ import annotations

import json
import logging
from typing import Any

from config.notify_sse_hub import NotifySseHub
from constants.fact_predicate_enum import FactPredicateEnum
from constants.sub_task_status_enum import SubTaskStatusEnum
from constants.sub_task_type_enum import SubTaskTypeEnum
from entity.domain.fact_domain import Fact
from entity.mongo.sub_task import SubTask
from entity.view.user_fact_update_request import UserFactUpdateRequest
from service.fact_service import FactService
from storage.job_storage import JobStorage
from storage.resume_storage import ResumeStorage
from tool.advisor_tools import build_advisor_tools
from tool.context import AdvisorToolContext
from tool.metadata import extra_missing_fields

from agent.ports import SubTaskPort, ToolResultCachePort
from agent.slot_clarify_rules import build_slot_clarify_message
from agent.state import AdvisorTurnState

logger = logging.getLogger(__name__)
_LOG_PARAMS_MAX = 1200


def _append_reply(state: AdvisorTurnState, message: str) -> None:
    msg = (message or "").strip()
    if not msg:
        return
    if not state.assistant_reply:
        state.assistant_reply = msg
        return
    if msg not in state.assistant_reply:
        state.assistant_reply = f"{state.assistant_reply}\n{msg}"


def _tool_required_fields(tool: Any) -> list[str]:
    try:
        schema = tool.get_input_jsonschema() or {}
        req = schema.get("required") or []
        return [str(x) for x in req if str(x).strip()]
    except Exception:
        return []


def _missing_fields(params: dict[str, Any], required: list[str]) -> list[str]:
    miss: list[str] = []
    for k in required:
        v = params.get(k)
        if v is None:
            miss.append(k)
            continue
        if isinstance(v, str) and not v.strip():
            miss.append(k)
    return miss


def _extra_missing_fields(tool_name: str, params: dict[str, Any]) -> list[str]:
    """工具级约束（非 JSON Schema required）补充校验。"""
    return extra_missing_fields(tool_name, params)


def _collect_missing_fields(
    *,
    tool_name: str,
    params: dict[str, Any],
    required: list[str],
) -> list[str]:
    base = _missing_fields(params, required)
    extra = _extra_missing_fields(tool_name, params)
    return list(dict.fromkeys([*base, *extra]))


def _params_for_log(params: dict[str, Any]) -> str:
    try:
        s = json.dumps(params, ensure_ascii=False, default=str)
    except Exception:
        s = repr(params)
    if len(s) <= _LOG_PARAMS_MAX:
        return s
    return f"{s[:_LOG_PARAMS_MAX]}... [truncated, total {len(s)} chars]"


def _tool_result_error_message(result: Any) -> str | None:
    """若工具返回标准 JSON 且 ok=false，则提取错误文案。"""
    if isinstance(result, dict):
        if result.get("ok") is False:
            return str(result.get("error") or "tool returned ok=false")
        return None
    if not isinstance(result, str):
        return None
    s = result.strip()
    if not s.startswith("{"):
        return None
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return None
    if isinstance(obj, dict) and obj.get("ok") is False:
        return str(obj.get("error") or "tool returned ok=false")
    return None


def _clarify_message(tool_name: str, missing_fields: list[str]) -> str:
    sk = missing_fields[0] if missing_fields else None
    return build_slot_clarify_message(
        slot_key=sk,
        missing_for_tool=tool_name,
        tool_name=tool_name,
    )


def _fact_confirm_message(params: dict[str, Any]) -> str:
    pred = str(params.get("predicate") or "").strip()
    cur = str(params.get("current_fact_content") or "").strip() or "（空）"
    new = str(params.get("new_fact_content") or "").strip() or "（空）"
    return (
        f"检测到事实 `{pred}` 可能需要更新。\n"
        f"当前：{cur}\n"
        f"建议更新为：{new}\n"
        "如果确认，请继续回复；如需修改，请直接给出新的信息。"
    )


async def _execute_slot(
    *,
    task_id: str,
    sub: SubTask,
    tools_by_name: dict[str, Any],
    sub_task_port: SubTaskPort,
    tool_cache: ToolResultCachePort | None,
    state: AdvisorTurnState,
) -> bool:
    sid = (sub.id or "").strip()
    if not sid:
        return False
    tool_name = (sub.tool_name or "").strip()
    tool = tools_by_name.get(tool_name)
    logger.info(
        "review execute_slot start task_id=%s sub_task_id=%s tool=%s",
        task_id,
        sid,
        tool_name or "（空）",
    )
    if tool is None:
        await sub_task_port.update_sub_task_fields(
            task_id,
            sid,
            set_fields={
                "status": SubTaskStatusEnum.failed.value,
                "error_message": f"unknown tool: {tool_name}",
            },
        )
        state.plan_user_notices.append(f"未知工具，跳过执行: {tool_name}")
        return False

    await sub_task_port.set_sub_task_status(task_id, sid, SubTaskStatusEnum.running)
    params = dict(sub.params or {})
    dep_sid = str(params.pop("_notify_on_success_sub_task_id", "") or "").strip()
    if tool_name == "notifyUser" and dep_sid:
        dep = await sub_task_port.get_sub_task(task_id, dep_sid)
        if dep is None:
            await sub_task_port.update_sub_task_fields(
                task_id,
                sid,
                set_fields={
                    "status": SubTaskStatusEnum.cancelled.value,
                    "error_message": f"notify dependency not found: {dep_sid}",
                },
            )
            return False
        if dep.status != SubTaskStatusEnum.success:
            await sub_task_port.update_sub_task_fields(
                task_id,
                sid,
                set_fields={
                    "status": SubTaskStatusEnum.cancelled.value,
                    "error_message": (
                        f"notify skipped because dependency {dep_sid} status={dep.status.value}"
                    ),
                },
            )
            return False
    try:
        result = await tool.ainvoke(params)
        err = _tool_result_error_message(result)
        if err:
            await sub_task_port.update_sub_task_fields(
                task_id,
                sid,
                set_fields={
                    "status": SubTaskStatusEnum.failed.value,
                    "error_message": err,
                },
            )
            state.warnings.append(f"review: 工具返回失败 {tool_name}: {err}")
            logger.warning(
                "review execute_slot failed_by_result task_id=%s sub_task_id=%s tool=%s error=%s",
                task_id,
                sid,
                tool_name,
                err,
            )
            return False
        await sub_task_port.update_sub_task_fields(
            task_id,
            sid,
            set_fields={"status": SubTaskStatusEnum.success.value},
        )
        if tool_cache is not None:
            key = f"tool_result:{task_id}:{sid}"
            await tool_cache.set(key, result)
            await sub_task_port.update_sub_task_fields(
                task_id,
                sid,
                set_fields={"result_cache_key": key},
            )
        logger.info(
            "review execute_slot success task_id=%s sub_task_id=%s tool=%s cached=%s",
            task_id,
            sid,
            tool_name,
            bool(tool_cache is not None),
        )
        return True
    except Exception as e:
        await sub_task_port.update_sub_task_fields(
            task_id,
            sid,
            set_fields={
                "status": SubTaskStatusEnum.failed.value,
                "error_message": str(e),
            },
        )
        state.warnings.append(f"review: 工具执行失败 {tool_name}: {e}")
        logger.warning(
            "review execute_slot exception task_id=%s sub_task_id=%s tool=%s error=%s",
            task_id,
            sid,
            tool_name,
            e,
        )
        return False


async def _process_created_slot(
    *,
    task_id: str,
    sub: SubTask,
    tools_by_name: dict[str, Any],
    sub_task_port: SubTaskPort,
    tool_cache: ToolResultCachePort | None,
    state: AdvisorTurnState,
) -> None:
    sid = (sub.id or "").strip()
    if not sid:
        return
    tool = tools_by_name.get((sub.tool_name or "").strip())
    required = _tool_required_fields(tool) if tool is not None else []
    params = dict(sub.params or {})
    missing = _collect_missing_fields(
        tool_name=str(sub.tool_name or ""),
        params=params,
        required=required,
    )
    logger.info(
        "review slot_check task_id=%s sub_task_id=%s tool=%s required=%s missing=%s params=%s",
        task_id,
        sid,
        str(sub.tool_name or "（空）"),
        required,
        missing,
        _params_for_log(params),
    )
    if not missing:
        logger.info(
            "review slot_ready_execute task_id=%s sub_task_id=%s tool=%s",
            task_id,
            sid,
            str(sub.tool_name or "（空）"),
        )
        await _execute_slot(
            task_id=task_id,
            sub=sub,
            tools_by_name=tools_by_name,
            sub_task_port=sub_task_port,
            tool_cache=tool_cache,
            state=state,
        )
        return

    await sub_task_port.set_sub_task_status(task_id, sid, SubTaskStatusEnum.waiting)
    logger.info(
        "review slot_missing_waiting task_id=%s sub_task_id=%s tool=%s missing=%s",
        task_id,
        sid,
        str(sub.tool_name or "（空）"),
        missing,
    )
    if await sub_task_port.count_open_clarifies(task_id) > 0:
        state.plan_user_notices.append(
            "当前任务已存在待处理澄清，跳过新增澄清任务。",
        )
        return
    msg = _clarify_message((sub.tool_name or "工具"), missing)
    clarify = SubTask(
        task_id=task_id,
        task_type=SubTaskTypeEnum.tool_slot_clarify,
        status=SubTaskStatusEnum.created,
        tool_name=sub.tool_name,
        params={
            "bind_task_id": sid,
            "missing_fields": missing,
            "supplement_params": {},
            "clarify_message": msg,
        },
    )
    clarify_id = await sub_task_port.insert_sub_task(clarify)
    logger.info(
        "review clarify_created task_id=%s bind_sub_task_id=%s clarify_id=%s missing=%s",
        task_id,
        sid,
        clarify_id,
        missing,
    )

async def _process_waiting_clarify(
    *,
    task_id: str,
    sub: SubTask,
    tools_by_name: dict[str, Any],
    sub_task_port: SubTaskPort,
    tool_cache: ToolResultCachePort | None,
    state: AdvisorTurnState,
) -> None:
    clarify_task_id = (sub.id or "").strip()
    if not clarify_task_id:
        return
    p = dict(sub.params or {})
    bind_id = str(p.get("bind_task_id") or "").strip()
    if not bind_id:
        return
    slot_task = await sub_task_port.get_sub_task(task_id, bind_id)
    if slot_task is None:
        return

    supplement = p.get("supplement_params")
    supplements = dict(supplement) if isinstance(supplement, dict) else {}
    if not supplements:
        logger.info(
            "review clarify_waiting_skip_empty task_id=%s clarify_id=%s bind_id=%s",
            task_id,
            clarify_task_id,
            bind_id,
        )
        return
    merged_params = dict(slot_task.params or {})
    merged_params.update(supplements)
    await sub_task_port.update_sub_task_fields(
        task_id,
        bind_id,
        set_fields={"params": merged_params},
    )

    tool = tools_by_name.get((slot_task.tool_name or "").strip())
    required = _tool_required_fields(tool) if tool is not None else []
    missing = _collect_missing_fields(
        tool_name=str(slot_task.tool_name or ""),
        params=merged_params,
        required=required,
    )
    logger.info(
        "review clarify_merge_check task_id=%s clarify_id=%s bind_id=%s tool=%s required=%s missing=%s merged_params=%s",
        task_id,
        clarify_task_id,
        bind_id,
        str(slot_task.tool_name or "（空）"),
        required,
        missing,
        _params_for_log(merged_params),
    )
    if not missing:
        slot_task = slot_task.model_copy(update={"params": merged_params})
        ok = await _execute_slot(
            task_id=task_id,
            sub=slot_task,
            tools_by_name=tools_by_name,
            sub_task_port=sub_task_port,
            tool_cache=tool_cache,
            state=state,
        )
        if ok:
            await sub_task_port.update_sub_task_fields(
                task_id,
                bind_id,
                set_fields={
                    "params": merged_params,
                    "status": SubTaskStatusEnum.success.value,
                },
            )
            await sub_task_port.set_sub_task_status(
                task_id,
                clarify_task_id,
                SubTaskStatusEnum.success,
            )
            logger.info(
                "review clarify_bound_slot_executed task_id=%s clarify_id=%s bind_id=%s",
                task_id,
                clarify_task_id,
                bind_id,
            )
        return

    p["missing_fields"] = missing
    p["clarify_message"] = _clarify_message(str(slot_task.tool_name or "工具"), missing)
    await sub_task_port.update_sub_task_fields(task_id, clarify_task_id, set_fields={"params": p})
    _append_reply(state, str(p["clarify_message"]))
    logger.info(
        "review clarify_still_missing task_id=%s clarify_id=%s bind_id=%s missing=%s",
        task_id,
        clarify_task_id,
        bind_id,
        missing,
    )


async def _process_created_fact_confirm(
    *,
    task_id: str,
    sub: SubTask,
    sub_task_port: SubTaskPort,
    state: AdvisorTurnState,
) -> None:
    sid = (sub.id or "").strip()
    if not sid:
        return
    params = dict(sub.params or {})
    msg = _fact_confirm_message(params)
    params["confirm_message"] = msg
    _append_reply(state, msg)
    await sub_task_port.update_sub_task_fields(
        task_id,
        sid,
        set_fields={"status": SubTaskStatusEnum.waiting.value, "params": params},
    )


async def _process_waiting_fact_confirm(
    *,
    sub: SubTask,
    task_id: str,
    sub_task_port: SubTaskPort,
    fact_service: FactService,
    state: AdvisorTurnState,
) -> None:
    sid = (sub.id or "").strip()
    if not sid:
        return
    p = dict(sub.params or {})
    confirm_state = str(p.get("confirm_state") or "created").strip().lower()
    if confirm_state not in {"created", "agree", "disagree"}:
        confirm_state = "created"
    pred = str(p.get("predicate") or "").strip()
    val = str(p.get("value") or "").strip()
    if not pred or not val:
        return
    if confirm_state == "disagree":
        await sub_task_port.update_sub_task_fields(
            task_id,
            sid,
            set_fields={"status": SubTaskStatusEnum.cancelled.value},
        )
        _append_reply(state, f"已取消事实 `{pred}` 的更新。")
        return
    if confirm_state == "created":
        msg = _fact_confirm_message(p)
        p["confirm_message"] = msg
        await sub_task_port.update_sub_task_fields(
            task_id,
            sid,
            set_fields={"status": SubTaskStatusEnum.waiting.value, "params": p},
        )
        _append_reply(state, msg)
        return
    # confirm_state == agree
    new_content = str(p.get("new_fact_content") or "").strip() or val

    try:
        fact_no = Fact.generate_fact_no(state.user_id, pred)
        hit = await fact_service.get_fact_view(state.user_id, fact_no)
        if hit is None:
            state.plan_user_notices.append(f"未找到可更新事实: {pred}")
            return
        body = UserFactUpdateRequest(
            fact_no=fact_no,
            user_id=state.user_id,
            predicate=FactPredicateEnum(pred),
            value=val,
            content=new_content,
        )
        ok = await fact_service.update_fact(body)
        await sub_task_port.set_sub_task_status(
            task_id,
            sid,
            SubTaskStatusEnum.success if ok else SubTaskStatusEnum.failed,
        )
        if ok:
            _append_reply(state, f"已更新事实 `{pred}`。")
    except Exception as e:
        await sub_task_port.update_sub_task_fields(
            task_id,
            sid,
            set_fields={
                "status": SubTaskStatusEnum.failed.value,
                "error_message": str(e),
            },
        )
        state.warnings.append(f"review: 事实更新失败 {pred}: {e}")


async def run_review(
    *,
    state: AdvisorTurnState,
    sub_task_port: SubTaskPort | None,
    fact_service: FactService,
    job_storage: JobStorage,
    resume_storage: ResumeStorage,
    notify_sse_hub: NotifySseHub,
    tool_cache: ToolResultCachePort | None = None,
) -> None:
    """处理 created/waiting 子任务：工具执行、澄清追问、事实确认。"""
    if state.errors:
        return
    tid = (state.task_id or "").strip()
    if not tid or sub_task_port is None:
        return

    ctx = AdvisorToolContext(
        user_id=state.user_id,
        job_storage=job_storage,
        resume_storage=resume_storage,
        notify_sse_hub=notify_sse_hub,
    )
    tools = build_advisor_tools(ctx)
    tools_by_name = {t.name: t for t in tools}
    open_sub_tasks = await sub_task_port.list_open_sub_tasks(tid)
    logger.info(
        "review start task_id=%s open_sub_tasks=%s",
        tid,
        len(open_sub_tasks),
    )

    for sub in open_sub_tasks:
        logger.info(
            "review dispatch task_id=%s sub_task_id=%s type=%s status=%s tool=%s",
            tid,
            str(sub.id or ""),
            sub.task_type.value,
            sub.status.value,
            str(sub.tool_name or ""),
        )
        if sub.task_type == SubTaskTypeEnum.tool_call and sub.status == SubTaskStatusEnum.created:
            await _process_created_slot(
                task_id=tid,
                sub=sub,
                tools_by_name=tools_by_name,
                sub_task_port=sub_task_port,
                tool_cache=tool_cache,
                state=state,
            )
            continue

        if sub.task_type == SubTaskTypeEnum.tool_slot_clarify and sub.status == SubTaskStatusEnum.waiting:
            await _process_waiting_clarify(
                task_id=tid,
                sub=sub,
                tools_by_name=tools_by_name,
                sub_task_port=sub_task_port,
                tool_cache=tool_cache,
                state=state,
            )
            continue

        if sub.task_type == SubTaskTypeEnum.fact_confirm and sub.status == SubTaskStatusEnum.created:
            await _process_waiting_fact_confirm(
                sub=sub,
                task_id=tid,
                sub_task_port=sub_task_port,
                fact_service=fact_service,
                state=state,
            )
            continue
        if sub.task_type == SubTaskTypeEnum.fact_confirm and sub.status == SubTaskStatusEnum.waiting:
            await _process_waiting_fact_confirm(
                sub=sub,
                task_id=tid,
                sub_task_port=sub_task_port,
                fact_service=fact_service,
                state=state,
            )
            continue
    logger.info("review done task_id=%s", tid)

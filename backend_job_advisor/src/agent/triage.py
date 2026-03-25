"""分拣（Triage）：判断是否归属最近主任务；否则新建任务（设计文档 §9.2）。"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta

from entity.mongo.task import Task
from entity.redis.dialogue_message import DialogueMessage

from service.llm_service import LlmService

from constants.agent_constants import AgentConstants
from core.time_utils import now_shanghai
from agent.ports import TaskLifecyclePort
from agent.state import AdvisorTurnState

logger = logging.getLogger(__name__)

LoadDialogueFn = Callable[[str, str], Awaitable[list[DialogueMessage]]]


async def run_triage(
    *,
    user_id: str,
    user_input: str,
    state: AdvisorTurnState,
    llm_service: LlmService,
    task_port: TaskLifecyclePort | None,
    load_dialogue_for_task: LoadDialogueFn,
) -> None:
    """写入 ``state.task_id`` / ``state.task_is_new``。

    ``load_dialogue_for_task(user_id, task_id)`` 一般由 ``DialogueHistoryStorage.get_recent`` 适配。
    """
    state.user_id = user_id
    state.user_input = user_input

    if task_port is None:
        tid = str(uuid.uuid4())
        state.task_id = tid
        state.task_is_new = True
        state.warnings.append(
            "triage: TaskLifecyclePort 未注入，使用临时 task_id（待 Mongo tasks 仓储接入）"
        )
        logger.info("triage ephemeral task_id=%s user_id=%s", tid, user_id)
        return

    now = now_shanghai()
    since = now - timedelta(
        minutes=AgentConstants.TRIAGE_CANDIDATE_TASK_MAX_AGE_MINUTES
    )
    candidates = await task_port.list_candidate_tasks(
        user_id, created_after=since, limit=10
    )
    if not candidates:
        task_id = await task_port.create_task(
            Task(
                user_id=user_id,
                user_input=user_input,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        state.task_id = task_id
        state.task_is_new = True
        logger.info("triage new task_id=%s user_id=%s", task_id, user_id)
        return

    latest = candidates[0]
    tid = (latest.id or "").strip()
    if not tid:
        task_id = await task_port.create_task(
            Task(
                user_id=user_id,
                user_input=user_input,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        state.task_id = task_id
        state.task_is_new = True
        state.warnings.append("triage: 候选任务无有效 id，已新建任务")
        return

    history = await load_dialogue_for_task(user_id, tid)
    state.history_dialogue = history
    related = await llm_service._heuristic_same_topic(user_input, history)
    if related:
        state.task_id = tid
        state.task_is_new = False
        logger.info("triage attach task_id=%s user_id=%s", tid, user_id)
        return

    task_id = await task_port.create_task(
        Task(
            user_id=user_id,
            user_input=user_input,
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    state.task_id = task_id
    state.task_is_new = True

    logger.info("triage fork new task_id=%s user_id=%s", task_id, user_id)

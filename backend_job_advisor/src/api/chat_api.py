"""对话 API：接入 ``AdvisorPipeline``（设计文档 §11 ``chat_api`` / JSONL 流式）。"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from config.api.request_factory import (
    get_dialogue_history_storage,
    get_mongo_db,
    get_notify_sse_hub,
    get_redis_db,
)
from config.notify_sse_hub import NotifySseHub
from agent.state import AdvisorTurnState
from core.context import AdvisorPipelineDeps
from core.time_utils import today_range_shanghai
from core.pipeline import AdvisorPipeline
from service.fact_service import FactService, get_fact_service
from service.llm_service import LlmService, get_llm_service
from storage import (
    JobStorage,
    MongoDb,
    RedisDb,
    ResumeStorage,
    SubTaskStorage,
    TaskStorage,
    ToolResultCacheStorage,
)
from storage.dialogue_history_storage import DialogueHistoryStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatTurnRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str = Field(min_length=1, description="会话用户标识")
    message: str = Field(min_length=1, description="用户本轮输入")


class ChatTurnResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_id: str | None = None
    task_is_new: bool = False
    reply: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ChatGraphResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    engine: str = "langgraph"
    format: str = "mermaid"
    graph: str


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    task_id: str
    role: str
    content: str
    ts: str | None = None


def get_advisor_pipeline_deps(
    llm_service: Annotated[LlmService, Depends(get_llm_service)],
    dialogue: Annotated[DialogueHistoryStorage, Depends(get_dialogue_history_storage)],
    fact_service: Annotated[FactService, Depends(get_fact_service)],
    mongo: Annotated[MongoDb, Depends(get_mongo_db)],
    redis: Annotated[RedisDb, Depends(get_redis_db)],
    hub: Annotated[NotifySseHub, Depends(get_notify_sse_hub)],
) -> AdvisorPipelineDeps:
    return AdvisorPipelineDeps(
        llm_service=llm_service,
        dialogue_history_storage=dialogue,
        fact_service=fact_service,
        job_storage=JobStorage(mongo),
        resume_storage=ResumeStorage(mongo),
        notify_sse_hub=hub,
        task_port=TaskStorage(mongo),
        sub_task_port=SubTaskStorage(mongo),
        tool_cache=ToolResultCacheStorage(redis),
    )


PipelineDep = Annotated[AdvisorPipelineDeps, Depends(get_advisor_pipeline_deps)]


@router.get("/history", response_model=list[ChatHistoryItem])
async def get_chat_history(
    user_id: str,
    storage: Annotated[DialogueHistoryStorage, Depends(get_dialogue_history_storage)] = None,
) -> list[ChatHistoryItem]:
    rows = await storage.get_recent_days(user_id, days=1, limit=1000)
    day_start, day_end = today_range_shanghai()
    rows = [
        x
        for x in rows
        if (
            isinstance(x.get("ts"), datetime)
            and day_start <= x.get("ts") < day_end
        )
        or (
            not isinstance(x.get("ts"), datetime)
            and str(x.get("ts") or "").strip()[:10] == day_start.strftime("%Y-%m-%d")
        )
    ]
    out: list[ChatHistoryItem] = []
    for x in rows:
        ts = x.get("ts")
        out.append(
            ChatHistoryItem(
                user_id=str(x.get("user_id") or ""),
                task_id=str(x.get("task_id") or ""),
                role=str(x.get("role") or ""),
                content=str(x.get("content") or ""),
                ts=ts.isoformat() if hasattr(ts, "isoformat") else (str(ts) if ts else None),
            )
        )
    return out


@router.get("/graph", response_model=ChatGraphResponse)
async def get_chat_graph(deps: PipelineDep) -> ChatGraphResponse:
    """返回当前聊天流水线图（Mermaid），用于调试可视化。"""
    pipeline = AdvisorPipeline(deps)
    return ChatGraphResponse(graph=pipeline.get_graph_mermaid())


@router.post("/turn", response_model=ChatTurnResponse)
async def post_chat_turn(
    body: ChatTurnRequest,
    deps: PipelineDep,
) -> ChatTurnResponse:
    """单轮对话（同步 JSON）：执行 Triage → Plan → Review → Executor。"""
    pipeline = AdvisorPipeline(deps)
    state = await pipeline.run_turn(body.user_id.strip(), body.message.strip())
    return ChatTurnResponse(
        task_id=state.task_id,
        task_is_new=state.task_is_new,
        reply=state.assistant_reply,
        planned_sub_tasks=state.planned_sub_tasks,
        plan_user_notices=state.plan_user_notices,
        warnings=state.warnings,
        errors=state.errors,
    )


@router.post("/stream")
async def post_chat_stream(
    body: ChatTurnRequest,
    deps: PipelineDep,
) -> StreamingResponse:
    """JSON Lines 流式响应（设计文档 JSONL）：每行一个 JSON 对象，事件类型见 ``event`` 字段。"""

    async def ndjson() -> AsyncIterator[bytes]:
        pipeline = AdvisorPipeline(deps)
        state = await pipeline.run_turn(body.user_id.strip(), body.message.strip())

        def line(obj: dict) -> bytes:
            return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")

        yield line(
            {
                "event": "meta",
                "task_id": state.task_id,
                "task_is_new": state.task_is_new,
            }
        )
        if state.warnings:
            yield line({"event": "warnings", "items": state.warnings})
        if state.errors:
            yield line({"event": "errors", "items": state.errors})
        if state.planned_sub_tasks:
            yield line(
                {"event": "plan", "planned_sub_tasks": state.planned_sub_tasks}
            )
        if state.plan_user_notices:
            yield line(
                {"event": "plan_notices", "items": state.plan_user_notices}
            )
        if state.assistant_reply:
            yield line(
                {
                    "event": "message",
                    "role": "assistant",
                    "content": state.assistant_reply,
                }
            )
        yield line({"event": "done"})
        logger.info(
            "chat stream done user_id=%s task_id=%s",
            body.user_id,
            state.task_id,
        )

    return StreamingResponse(
        ndjson(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

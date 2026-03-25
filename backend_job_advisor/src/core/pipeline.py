"""求职顾问对话流水线：基于 LangGraph 编排多出口节点图（设计文档 §9.1）。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TypedDict

from constants.agent_constants import AgentConstants
from agent.executor import run_executor
from agent.plan import run_plan
from agent.review import run_review
from agent.state import AdvisorTurnState
from agent.triage import run_triage
from core.context import AdvisorPipelineDeps
from entity.redis.dialogue_message import DialogueMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger(__name__)

SHANGHAI_TZ = timezone(timedelta(hours=8))


def now_shanghai() -> datetime:
    return datetime.now(SHANGHAI_TZ)


class _PipelineGraphState(TypedDict):
    state: AdvisorTurnState


class AdvisorPipeline:
    """LangGraph 编排：Triage → Plan → Review，按条件到 Executor 或直接 END。"""

    def __init__(self, deps: AdvisorPipelineDeps) -> None:
        self._deps = deps
        self._checkpointer = InMemorySaver()
        self._graph = self._build_graph()

    async def _load_dialogue(self, user_id: str, task_id: str):
        del task_id
        return await self._deps.dialogue_history_storage.get_recent(
            user_id,
            limit=AgentConstants.DEFAULT_DIALOGUE_HISTORY_LIMIT,
        )

    async def _persist_user_message(self, s: AdvisorTurnState) -> None:
        if s.dialogue_user_persisted:
            return
        tid = (s.task_id or "").strip()
        msg = (s.user_input or "").strip()
        if not tid or not msg:
            return
        now = now_shanghai()
        await self._deps.dialogue_history_storage.append(
            s.user_id,
            DialogueMessage(role="user", content=msg, ts=now),
            task_id=tid,
        )
        s.dialogue_user_persisted = True

    async def _persist_assistant_message(self, s: AdvisorTurnState) -> None:
        if s.dialogue_assistant_persisted:
            return
        tid = (s.task_id or "").strip()
        msg = (s.assistant_reply or "").strip()
        if not tid or not msg:
            return
        now = now_shanghai()
        await self._deps.dialogue_history_storage.append(
            s.user_id,
            DialogueMessage(role="assistant", content=msg, ts=now),
            task_id=tid,
        )
        s.dialogue_assistant_persisted = True

    async def _node_triage(self, gs: _PipelineGraphState) -> _PipelineGraphState:
        s = gs["state"]
        await run_triage(
            user_id=s.user_id,
            user_input=s.user_input,
            state=s,
            llm_service=self._deps.llm_service,
            task_port=self._deps.task_port,
            load_dialogue_for_task=self._load_dialogue,
        )
        return {"state": s}

    async def _node_plan(self, gs: _PipelineGraphState) -> _PipelineGraphState:
        s = gs["state"]
        await run_plan(
            fact_service=self._deps.fact_service,
            llm_service=self._deps.llm_service,
            dialogue_storage=self._deps.dialogue_history_storage,
            job_storage=self._deps.job_storage,
            resume_storage=self._deps.resume_storage,
            notify_sse_hub=self._deps.notify_sse_hub,
            state=s,
            sub_task_port=self._deps.sub_task_port,
        )
        return {"state": s}

    async def _node_review(self, gs: _PipelineGraphState) -> _PipelineGraphState:
        s = gs["state"]
        await run_review(
            state=s,
            sub_task_port=self._deps.sub_task_port,
            fact_service=self._deps.fact_service,
            job_storage=self._deps.job_storage,
            resume_storage=self._deps.resume_storage,
            notify_sse_hub=self._deps.notify_sse_hub,
            tool_cache=self._deps.tool_cache,
        )
        await self._persist_assistant_message(s)
        return {"state": s}

    async def _node_executor(self, gs: _PipelineGraphState) -> _PipelineGraphState:
        s = gs["state"]
        await run_executor(
            llm_service=self._deps.llm_service,
            fact_service=self._deps.fact_service,
            dialogue_storage=self._deps.dialogue_history_storage,
            sub_task_port=self._deps.sub_task_port,
            tool_cache=self._deps.tool_cache,
            state=s,
        )
        await self._persist_assistant_message(s)
        return {"state": s}

    def _route_after_review(self, gs: _PipelineGraphState) -> str:
        s = gs["state"]
        if s.errors:
            return "end"
        if s.assistant_reply:
            return "end"
        return "executor"

    def _build_graph(self):
        graph = StateGraph(_PipelineGraphState)
        graph.add_node("triage", self._node_triage)
        graph.add_node("plan", self._node_plan)
        graph.add_node("review", self._node_review)
        graph.add_node("executor", self._node_executor)
        graph.add_edge(START, "triage")
        graph.add_edge("triage", "plan")
        graph.add_edge("plan", "review")
        graph.add_conditional_edges(
            "review",
            self._route_after_review,
            {"executor": "executor", "end": END},
        )
        graph.add_edge("executor", END)
        return graph.compile(checkpointer=self._checkpointer)

    @staticmethod
    def _thread_id(user_id: str) -> str:
        return f"advisor:{user_id.strip() or 'unknown'}"

    def get_graph_mermaid(self) -> str:
        return self._graph.get_graph().draw_mermaid()

    async def run_turn(self, user_id: str, user_input: str) -> AdvisorTurnState:
        """处理单轮用户输入，支持多出口路由与基于 checkpoint 的异常恢复。"""
        state = AdvisorTurnState(user_id=user_id, user_input=user_input)
        cfg = {"configurable": {"thread_id": self._thread_id(user_id)}}
        try:
            out = await self._graph.ainvoke({"state": state}, config=cfg)
            final_state = out.get("state", state)
            await self._persist_user_message(final_state)
            logger.info(
                "pipeline turn user_id=%s task_id=%s errors=%s",
                user_id,
                final_state.task_id,
                len(final_state.errors),
            )
            return final_state
        except Exception as e:
            logger.exception("pipeline graph failed user_id=%s", user_id)
            last = self._checkpointer.get_tuple(cfg)
            if last and getattr(last, "checkpoint", None):
                vals = last.checkpoint.get("channel_values", {})
                recovered = vals.get("state")
                if isinstance(recovered, AdvisorTurnState):
                    await self._persist_user_message(recovered)
                    recovered.errors.append(f"pipeline recovered after graph error: {e}")
                    return recovered
                if isinstance(recovered, dict):
                    rs = AdvisorTurnState.model_validate(recovered)
                    await self._persist_user_message(rs)
                    rs.errors.append(f"pipeline recovered after graph error: {e}")
                    return rs
            await self._persist_user_message(state)
            state.errors.append(f"pipeline: {e}")
            return state

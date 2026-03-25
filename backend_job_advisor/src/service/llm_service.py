"""LangChain 能力门面：对业务层暴露聊天模型与 Embedding，与 lifespan 中的单例一致。"""

from __future__ import annotations

import json
import logging
from typing import Any, Sequence

from fastapi import Depends
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel, Field

from config.api.request_factory import get_llm, get_openai_embeddings
from constants.fact_predicate_enum import FactPredicateEnum
from entity.agent.plan_models import PlanAdvisorTurnResult
from entity.domain.fact_domain import Fact
from entity.redis.dialogue_message import DialogueMessage

logger = logging.getLogger(__name__)

_LOG_TEXT_MAX = 12_000
_LOG_KWARGS_MAX = 2_000


def _truncate_text(text: str, max_len: int = _LOG_TEXT_MAX) -> str:
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}... [truncated, total {len(text)} chars]"


def _messages_to_log_payload(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
    """将 LangChain 消息转为可 JSON 日志的结构（正文过长则截断）。"""
    rows: list[dict[str, Any]] = []
    for m in messages:
        role = getattr(m, "type", None) or m.__class__.__name__
        raw = getattr(m, "content", "")
        if isinstance(raw, list):
            content = _truncate_text(json.dumps(raw, ensure_ascii=False))
        elif isinstance(raw, str):
            content = _truncate_text(raw)
        else:
            content = _truncate_text(str(raw))
        row: dict[str, Any] = {"role": role, "content": content}
        if getattr(m, "name", None):
            row["name"] = m.name
        rows.append(row)
    return rows


def _kwargs_for_log(kwargs: dict[str, Any]) -> str:
    try:
        s = json.dumps(kwargs, ensure_ascii=False, default=str)
    except TypeError:
        s = str(kwargs)
    return _truncate_text(s, _LOG_KWARGS_MAX)


def _assistant_response_to_log(msg: BaseMessage) -> dict[str, Any]:
    out: dict[str, Any] = {"class": msg.__class__.__name__}
    c = getattr(msg, "content", None)
    if isinstance(c, str):
        out["content"] = _truncate_text(c)
    elif c is not None:
        out["content"] = _truncate_text(json.dumps(c, ensure_ascii=False, default=str))
    tcalls = getattr(msg, "tool_calls", None)
    if tcalls:
        out["tool_calls"] = tcalls
    ru = getattr(msg, "response_metadata", None)
    if ru:
        out["response_metadata"] = ru
    return out


class _SameTopicJudgment(BaseModel):
    """供 Triage 结构化输出解析。"""

    same_topic: bool = Field(
        description="最新用户输入是否仍属于与上文同一连续求职咨询话题",
    )


class _ExtractedFact(BaseModel):
    """事实抽取结果单项。"""

    predicate: FactPredicateEnum = Field(description="事实谓词（FactPredicateEnum 枚举值）")
    value: str = Field(default="", description="结构化值（便于后续检索/过滤）")
    content: str = Field(default="", description="用户原话归一化后的事实表述")
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="抽取置信度，范围 0~1",
    )


class _ExtractedFacts(BaseModel):
    facts: list[_ExtractedFact] = Field(default_factory=list)


class LlmService:
    """封装 ``ChatOpenAI`` 与 ``OpenAIEmbeddings``，便于链式编排（LCEL）与依赖注入。"""

    def __init__(self, chat_model: ChatOpenAI, embeddings: OpenAIEmbeddings) -> None:
        self._chat = chat_model
        self._embeddings = embeddings

    @property
    def chat_model(self) -> ChatOpenAI:
        """用于 ``chat_model | parser`` 等 LangChain Runnable 组合。"""
        return self._chat

    @property
    def embeddings(self) -> OpenAIEmbeddings:
        """与向量库写入 / 检索共用，须保持模型与维度一致。"""
        return self._embeddings

    def invoke(self, messages: Sequence[BaseMessage], **kwargs: Any) -> BaseMessage:
        payload = _messages_to_log_payload(messages)
        logger.info(
            "LLM invoke 入参 messages=%s kwargs=%s",
            json.dumps(payload, ensure_ascii=False),
            _kwargs_for_log(dict(kwargs)),
        )
        resp = self._chat.invoke(list(messages), **kwargs)
        logger.info(
            "LLM invoke 出参 response=%s",
            json.dumps(_assistant_response_to_log(resp), ensure_ascii=False, default=str),
        )
        return resp

    async def ainvoke(self, messages: Sequence[BaseMessage], **kwargs: Any) -> BaseMessage:
        payload = _messages_to_log_payload(messages)
        logger.info(
            "LLM ainvoke 入参 messages=%s kwargs=%s",
            json.dumps(payload, ensure_ascii=False),
            _kwargs_for_log(dict(kwargs)),
        )
        resp = await self._chat.ainvoke(list(messages), **kwargs)
        logger.info(
            "LLM ainvoke 出参 response=%s",
            json.dumps(_assistant_response_to_log(resp), ensure_ascii=False, default=str),
        )
        return resp

    def embed_query(self, text: str) -> list[float]:
        t = text or ""
        logger.info(
            "Embedding embed_query 入参 len=%s preview=%s",
            len(t),
            _truncate_text(t, 300),
        )
        vec = self._embeddings.embed_query(text)
        logger.info("Embedding embed_query 出参 dim=%s", len(vec))
        return vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        total = sum(len(x or "") for x in texts)
        logger.info(
            "Embedding embed_documents 入参 count=%s total_chars=%s",
            len(texts),
            total,
        )
        vecs = self._embeddings.embed_documents(texts)
        logger.info(
            "Embedding embed_documents 出参 batch_size=%s dim=%s",
            len(vecs),
            len(vecs[0]) if vecs else 0,
        )
        return vecs

    async def aembed_query(self, text: str) -> list[float]:
        t = text or ""
        logger.info(
            "Embedding aembed_query 入参 len=%s preview=%s",
            len(t),
            _truncate_text(t, 300),
        )
        vec = await self._embeddings.aembed_query(text)
        logger.info("Embedding aembed_query 出参 dim=%s", len(vec))
        return vec

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        total = sum(len(x or "") for x in texts)
        logger.info(
            "Embedding aembed_documents 入参 count=%s total_chars=%s",
            len(texts),
            total,
        )
        vecs = await self._embeddings.aembed_documents(texts)
        logger.info(
            "Embedding aembed_documents 出参 batch_size=%s dim=%s",
            len(vecs),
            len(vecs[0]) if vecs else 0,
        )
        return vecs

    async def _heuristic_same_topic(
        self,
        user_input: str,
        history: Sequence[DialogueMessage],
    ) -> bool:
        """Triage 用：用 ``self._chat`` 判定当前输入是否与近期对话同属一主题（设计文档 §9.2）。

        无历史或调用失败时返回 ``True``（保守归入当前任务，避免误拆会话）。
        """
        u = (user_input or "").strip()
        if not u:
            return True
        if not history:
            return True

        lines = [f"{m.role}: {m.content}" for m in history[-12:] if m.content]
        history_text = "\n".join(lines) if lines else "（无正文）"

        messages = [
            SystemMessage(
                content=(
                    "你是求职顾问对话分拣器。根据「近期对话」与「用户最新一句」，判断是否仍属于"
                    "同一次连续的求职咨询会话（同一主题、同一上下文）。若用户明显换话题、"
                    "开始无关闲聊或全新求职诉求，则不属于同一主题。仅依据结构化字段输出，不要多余文字。"
                )
            ),
            HumanMessage(
                content=(
                    f"【近期对话】\n{history_text}\n\n"
                    f"【用户最新输入】\n{u}\n\n"
                    "请判断最新输入是否仍属于与上文同一话题。"
                )
            ),
        ]

        try:
            logger.info(
                "LLM same_topic 入参 messages=%s",
                json.dumps(_messages_to_log_payload(messages), ensure_ascii=False),
            )
            runnable = self._chat.bind(temperature=0).with_structured_output(
                _SameTopicJudgment,
                method="function_calling",
            )
            out = await runnable.ainvoke(messages)
            if isinstance(out, _SameTopicJudgment):
                raw_log: Any = out.model_dump()
            elif isinstance(out, dict):
                raw_log = json.dumps(out, ensure_ascii=False, default=str)
            else:
                raw_log = repr(out)
            logger.info("LLM same_topic 出参 raw=%s", raw_log)
            if isinstance(out, _SameTopicJudgment):
                return out.same_topic
            if isinstance(out, dict):
                return bool(out.get("same_topic", True))
            return True
        except Exception as e:
            logger.warning("same_topic LLM 判定失败，默认归入当前任务: %s", e)
            return True

    async def plan_advisor_subtasks(
        self,
        *,
        user_input: str,
        history_block: str,
        facts_block: str,
        tools_spec: list[dict[str, Any]],
        open_sub_tasks_block: str,
    ) -> PlanAdvisorTurnResult:
        """根据事实、可用工具、未完成子任务与对话，解析本轮意图（可混合）。"""
        tools_json = json.dumps(tools_spec, ensure_ascii=False, indent=2)
        messages = [
            SystemMessage(
                content=(
                    "你是求职顾问的 Plan 规划器。基于用户输入、历史、事实、可用工具和未完成子任务，"
                    "输出结构化 items（每项必须有 kind）。\n\n"
                    "本阶段仅处理 3 类任务：\n"
                    "1) slot（槽位解析）\n"
                    "- 仅当用户明确要执行某工具时输出 slot。\n"
                    "- tool_name 必须与可用工具 name 完全一致。\n"
                    "- tool_params 只允许工具 parameters.properties 中定义的键。\n"
                    "- 未识别参数、无关参数、臆造参数一律不要输出。\n"
                    "- 参数值必须是原生 JSON 类型（string/number/boolean/object/array/null），"
                    "严禁把 object/array 序列化成 JSON 字符串。\n\n"
                    "2) clarify（槽位澄清补充）\n"
                    "- 仅用于“更新已存在的澄清任务”，不新建澄清。\n"
                    "- supplement_params 仅填写本轮新增/修正参数；tool_name 与绑定任务一致。\n"
                    "3) fact_confirm（事实确认）\n"
                    "- 结合现有事实(以predicate作为key检索)，若用户表述与已存事实冲突/改写，输出 fact_confirm。\n"
                    "- 对应的检索事实为空时，则忽略\n"
                    "- 必填：predicate、value、current_fact_content、new_fact_content。\n"
                    "- 新建确认任务时：confirm_state=created，bind_task_id 置空。\n"
                    "- 更新已有确认任务时：填写 bind_task_id；用户同意=confirm_state=agree，"
                    "用户不同意=confirm_state=disagree。\n\n"
                    "若本轮不属于以上 3 类任务，返回空 items。"
                )
            ),
            HumanMessage(
                content=(
                    f"【用户最新输入】\n{(user_input or '').strip() or '（空）'}\n\n"
                    f"【近期对话】\n{history_block or '（无）'}\n\n"
                    f"【检索事实 JSON】\n{facts_block or '[]'}\n\n"
                    f"【可用工具】\n{tools_json}\n\n"
                    f"【未完成子任务 created/waiting】\n{open_sub_tasks_block or '[]'}\n\n"
                    "请输出本轮 items。"
                )
            ),
        ]
        runnable = self._chat.bind(temperature=0).with_structured_output(
            PlanAdvisorTurnResult,
            method="function_calling",
        )
        out = await runnable.ainvoke(messages)
        logger.info("LLM plan_advisor_subtasks 出参 非预期类型=%s，返回空 items", type(out).__name__)
        if isinstance(out, PlanAdvisorTurnResult):
            return out
        if isinstance(out, dict):
            parsed = PlanAdvisorTurnResult.model_validate(out)
            return parsed
        return PlanAdvisorTurnResult(items=[])

    async def extract_facts_from_user_input(
        self,
        *,
        user_id: str,
        user_input: str,
    ) -> list[Fact]:
        """从用户输入抽取结构化事实，返回待 upsert 的事实列表。"""
        text = (user_input or "").strip()
        if not text:
            return []
        runnable = self._chat.bind(temperature=0).with_structured_output(_ExtractedFacts)
        out = await runnable.ainvoke(
            [
                SystemMessage(
                    content=(
                        "你是事实抽取器。仅从用户原话中抽取可结构化的求职事实。"
                        "输出 facts 列表；每条含 predicate、value、content、confidence。"
                        "若无可抽取事实，返回空列表。不要杜撰。"
                    )
                ),
                HumanMessage(content=text),
            ]
        )
        rows = out.facts if isinstance(out, _ExtractedFacts) else []
        facts: list[Fact] = []
        for x in rows:
            val = (x.value or "").strip()
            cont = (x.content or "").strip() or val
            if not val and not cont:
                continue
            extracted = Fact(
                user_id=user_id,
                predicate=x.predicate,
                value=val,
                content=cont,
                confidence=float(x.confidence),
            )
            # 抽取场景走“新增/覆盖”语义：避免因为自动 fact_no 进入仅更新分支。
            facts.append(extracted.model_copy(update={"fact_no": None}))
        return facts


def get_llm_service(
    chat: ChatOpenAI = Depends(get_llm),
    embeddings: OpenAIEmbeddings = Depends(get_openai_embeddings),
) -> LlmService:
    return LlmService(chat, embeddings)

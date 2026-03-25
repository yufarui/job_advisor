"""求职顾问 Agent 工具集（设计文档 §10），基于 LangChain ``@tool`` 注册。"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any

import httpx
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field, ValidationError, model_validator

from entity.view.resume_update_request import ResumeUpdateRequest, ResumeUpdateToolInput
from entity.view.user_job_update_request import UserJobUpdateRequest, UserJobUpdateToolInput
from config.notify_sse_hub import build_notify_push_payload
from tool.context import AdvisorToolContext

logger = logging.getLogger(__name__)

_DUCKDUCKGO_API = "https://api.duckduckgo.com/"
_DDG_TIMEOUT = 12.0


def _json_ok(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _json_err(msg: str) -> str:
    return _json_ok({"ok": False, "error": msg})


class SearchJobsToolInput(BaseModel):
    """searchJobs 入参：biz_ids 与 title 至少提供一项。"""

    biz_ids: list[str] | None = Field(default=None, description="职位业务 ID 列表（优先）")
    title: str | None = Field(default=None, description="职位标题（仅在 biz_ids 为空时使用）")
    title_match_limit: int = Field(default=5, ge=1, le=50, description="title 模糊匹配上限")

    @model_validator(mode="after")
    def validate_one_of_biz_ids_or_title(self) -> "SearchJobsToolInput":
        ids = [x.strip() for x in (self.biz_ids or []) if x and str(x).strip()]
        t = (self.title or "").strip()
        if not ids and not t:
            raise ValueError("biz_ids 或 title 至少提供一项")
        self.biz_ids = ids or None
        self.title = t or None
        return self


def build_tools_spec_for_plan(tools: Sequence[BaseTool]) -> list[dict[str, Any]]:
    """从 ``@tool`` 生成的 ``BaseTool`` 抽取名称、说明与入参 JSON Schema，供 Plan 阶段 LLM 使用。"""

    specs: list[dict[str, Any]] = []
    for t in tools:
        row: dict[str, Any] = {
            "name": t.name,
            "description": (t.description or "").strip(),
        }
        try:
            row["parameters"] = t.get_input_jsonschema()
        except Exception:
            row["parameters"] = {
                "type": "object",
                "properties": dict(getattr(t, "args", {}) or {}),
            }
        specs.append(row)
    return specs


def build_advisor_tools(ctx: AdvisorToolContext) -> list[BaseTool]:
    """根据上下文构造可绑定到 ChatModel 的工具列表（异步 I/O，需在 async Agent 中调用）。"""

    @tool(
        "searchJobs",
        args_schema=SearchJobsToolInput,
        infer_schema=False,
    )
    async def search_jobs(**kwargs: Any) -> str:
        """按业务编号列表或职位标题查询职位；优先使用业务编号。biz_ids 非空时按列表顺序返回命中的职位；否则用 title 模糊匹配。"""
        try:
            tool_in = SearchJobsToolInput.model_validate(kwargs)
            ids = [x.strip() for x in (tool_in.biz_ids or []) if x and str(x).strip()]
            if ids:
                jobs = await ctx.job_storage.find_jobs_by_biz_ids_ordered(ids)
                return _json_ok(
                    {
                        "ok": True,
                        "mode": "biz_id",
                        "count": len(jobs),
                        "jobs": [j.model_dump(mode="json") for j in jobs],
                    }
                )
            t = (tool_in.title or "").strip()
            if not t:
                return _json_err("必须提供 biz_ids 或 title 之一")
            lim = max(1, min(int(tool_in.title_match_limit), 50))
            jobs = await ctx.job_storage.find_jobs_by_title_regex(t, limit=lim)
            return _json_ok(
                {
                    "ok": True,
                    "mode": "title",
                    "count": len(jobs),
                    "jobs": [j.model_dump(mode="json") for j in jobs],
                }
            )
        except ValidationError as e:
            return _json_err(f"参数校验失败: {e}")
        except Exception as e:
            logger.exception("searchJobs failed")
            return _json_err(str(e))

    @tool("searchResume")
    async def search_resume() -> str:
        """按当前会话用户 user_id 查询唯一简历（1:1）。"""
        try:
            r = await ctx.resume_storage.find_by_user_id(ctx.user_id)
            if r is None:
                return _json_ok({"ok": True, "found": False, "resume": None})
            return _json_ok(
                {"ok": True, "found": True, "resume": r.model_dump(mode="json")}
            )
        except Exception as e:
            logger.exception("searchResume failed")
            return _json_err(str(e))

    @tool("searchCompany")
    async def search_company(
        company_name: str,
    ) -> str:
        """查询公司公开摘要信息；通过 DuckDuckGo Instant Answer API（可视为轻量联网检索，无 API Key）。"""
        q = company_name.strip()
        if not q:
            return _json_err("company_name 不能为空")
        params = {
            "q": q,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
        try:
            async with httpx.AsyncClient(timeout=_DDG_TIMEOUT) as client:
                r = await client.get(_DUCKDUCKGO_API, params=params)
                r.raise_for_status()
                body = r.json()
            logger.info("searchCompany body: %s", json.dumps(body, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.exception("searchCompany failed")
            return _json_err(str(e))
        abstract = body.get("Abstract") or body.get("Definition")
        url = body.get("AbstractURL") or body.get("DefinitionURL")
        return _json_ok(
            {
                "ok": True,
                "company_name": q,
                "region": "zh-cn",
                "abstract": abstract,
                "url": url,
                "source": "duckduckgo",
                "related_topics": [
                    t.get("Text")
                    for t in (body.get("RelatedTopics") or [])[:5]
                    if isinstance(t, dict) and t.get("Text")
                ],
            }
        )

    @tool(
        "updateJobs",
        args_schema=UserJobUpdateToolInput,
        infer_schema=False,
    )
    async def update_jobs(**kwargs: Any) -> str:
        """更新当前用户与某职位（biz_id）的关系。入参结构与 ``UserJobUpdateToolInput`` / ``UserJobUpdateRequest``（不含 user_id）一致；勿传 user_id。"""
        try:
            tool_in = UserJobUpdateToolInput.model_validate(kwargs)
            b = tool_in.biz_id.strip()
            if not b:
                return _json_err("biz_id 不能为空")
            body = UserJobUpdateRequest(
                user_id=ctx.user_id,
                biz_id=b,
                status=tool_in.status,
                attention_level=tool_in.attention_level,
                note=tool_in.note,
            )
            if not body.to_mongo_set():
                return _json_err("至少需要提供 status、attention_level、note 之一")
            ok = await ctx.job_storage.update_user_job_by_user_and_biz(body)
            return _json_ok({"ok": ok, "biz_id": b, "updated": ok})
        except ValidationError as e:
            return _json_err(f"参数校验失败: {e}")
        except Exception as e:
            logger.exception("updateJobs failed")
            return _json_err(str(e))

    @tool(
        "updateResume",
        args_schema=ResumeUpdateToolInput,
        infer_schema=False
    )
    async def update_resume(**kwargs: Any) -> str:
        """同 description：结构化参数与 ResumeUpdateToolInput JSON Schema 一致。"""
        try:
            tool_in = ResumeUpdateToolInput.model_validate(kwargs)
            patch = tool_in.model_dump(
                mode="python",
                exclude_unset=True,
                exclude_none=True,
            )
            if not patch:
                return _json_err(
                    "至少提供一项可更新字段：basic_info、work_experience、education、skills、job_intent 之一"
                )
            body = ResumeUpdateRequest(user_id=ctx.user_id, **patch)
            payload = body.to_mongo_set()
            if not payload:
                return _json_err("无有效字段可更新")
            ok = await ctx.resume_storage.update_resume_by_user_id(body)
            return _json_ok({"ok": ok, "updated": ok})
        except ValidationError as e:
            return _json_err(f"参数校验失败: {e}")
        except Exception as e:
            logger.exception("updateResume failed")
            return _json_err(str(e))

    @tool("notifyUser")
    async def notify_user(
        message: str,
        severity: str = "info",
        event_type: str = "toast",
    ) -> str:
        """向前端推送提示（默认 toast 弹窗）：经 ``NotifySseHub.publish`` 发出，与 ``POST /notify/user/{user_id}/push`` 等价。"""
        msg = message.strip()
        if not msg:
            return _json_err("message 不能为空")
        et = (event_type or "toast").strip().lower() or "toast"
        if et not in {"toast", "banner"}:
            et = "toast"
        payload = build_notify_push_payload(
            msg,
            severity=severity,
            event_type=et,
        )
        delivered = await ctx.notify_sse_hub.publish(ctx.user_id, payload)
        logger.info(
            "notifyUser publish user_id=%s delivered=%s severity=%s message=%s",
            ctx.user_id,
            delivered,
            payload["severity"],
            msg[:200],
        )
        return "success"

    return [
        search_jobs,
        search_resume,
        search_company,
        update_jobs,
        update_resume,
        notify_user,
    ]

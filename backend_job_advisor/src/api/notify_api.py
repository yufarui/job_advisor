"""用户通知：Server-Sent Events（SSE），供前端长连接收服务端推送（设计文档 §11 notify_api）。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from config.api.request_factory import get_notify_sse_hub
from config.notify_sse_hub import NotifySseHub, build_notify_push_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notify", tags=["notify"])

NotifyHubDep = Annotated[NotifySseHub, Depends(get_notify_sse_hub)]

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

_KEEPALIVE_SECONDS = 25.0


class NotifyPushRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str = Field(min_length=1, description="展示给用户的提示文案")
    severity: str = Field(default="info", description="如 info | success | warning | error")
    event_type: str = Field(
        default="toast",
        description="前端可据此选择交互，如 toast | banner",
    )


class NotifyPushResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    delivered: int = Field(ge=0, description="当前该用户在线 SSE 连接数中成功入队的数量")


async def _sse_event_stream(
    user_id: str,
    hub: NotifySseHub,
) -> AsyncIterator[str]:
    queue = await hub.subscribe(user_id)
    try:
        yield "retry: 5000\n\n"
        while True:
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_SECONDS)
                yield chunk
            except asyncio.TimeoutError:
                yield ": ping\n\n"
    finally:
        await hub.unsubscribe(user_id, queue)


@router.get("/user/{user_id}/stream")
async def notify_sse_stream(
    user_id: str,
    hub: NotifyHubDep,
) -> StreamingResponse:
    """建立 SSE 长连接；事件体为 JSON（``message`` / ``severity`` / ``event_type`` / ``ts`` 等）。"""

    uid = user_id.strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id required")

    gen = _sse_event_stream(uid, hub)
    return StreamingResponse(
        gen,
        media_type="text/event-stream; charset=utf-8",
        headers=dict(_SSE_HEADERS),
    )


@router.post("/user/{user_id}/push", response_model=NotifyPushResponse)
async def notify_push(
    user_id: str,
    body: NotifyPushRequest,
    hub: NotifyHubDep,
) -> NotifyPushResponse:
    """服务端向指定用户推送一条通知（所有该用户的 SSE 连接均可收到）。

    生产环境应增加鉴权（仅服务账号或同用户会话可调用）。
    """
    uid = user_id.strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id required")

    payload = build_notify_push_payload(
        body.message,
        severity=body.severity,
        event_type=body.event_type,
    )
    n = await hub.publish(uid, payload)
    logger.info("notify push user_id=%s delivered=%s", uid, n)
    return NotifyPushResponse(delivered=n)

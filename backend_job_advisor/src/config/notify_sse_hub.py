"""进程内 SSE 通知中心：按 ``user_id`` fan-out 到该用户所有已连接客户端。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from core.time_utils import now_shanghai

logger = logging.getLogger(__name__)


def build_notify_push_payload(
    message: str,
    *,
    severity: str = "info",
    event_type: str = "toast",
) -> dict[str, Any]:
    """与 ``POST /notify/user/{user_id}/push``、SSE ``data`` 行语义一致。"""
    return {
        "message": message.strip(),
        "severity": (severity or "info").strip() or "info",
        "event_type": (event_type or "toast").strip() or "toast",
        "ts": now_shanghai().isoformat(),
    }

_DEFAULT_QUEUE_MAX = 256


class NotifySseHub:
    """每个 SSE 连接对应一个 ``asyncio.Queue``；``publish`` 向该用户全部队列投递同一条帧。"""

    def __init__(self, *, queue_maxsize: int = _DEFAULT_QUEUE_MAX) -> None:
        self._queue_maxsize = max(8, int(queue_maxsize))
        self._lock = asyncio.Lock()
        self._by_user: dict[str, list[asyncio.Queue[str]]] = {}

    async def subscribe(self, user_id: str) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=self._queue_maxsize)
        async with self._lock:
            self._by_user.setdefault(user_id, []).append(q)
        logger.debug(
            "notify sse subscribe user_id=%s subs=%s",
            user_id,
            len(self._by_user.get(user_id, [])),
        )
        return q

    async def unsubscribe(self, user_id: str, queue: asyncio.Queue[str]) -> None:
        async with self._lock:
            subs = self._by_user.get(user_id)
            if not subs:
                return
            if queue in subs:
                subs.remove(queue)
            if not subs:
                del self._by_user[user_id]
        logger.debug("notify sse unsubscribe user_id=%s", user_id)

    def _format_sse(self, payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"

    async def publish(self, user_id: str, payload: dict[str, Any]) -> int:
        """向 ``user_id`` 下所有连接推送一条事件；返回成功入队的连接数。"""
        chunk = self._format_sse(payload)
        async with self._lock:
            subs = list(self._by_user.get(user_id, []))
        delivered = 0
        for q in subs:
            try:
                q.put_nowait(chunk)
                delivered += 1
            except asyncio.QueueFull:
                logger.warning("notify sse queue full, drop for user_id=%s", user_id)
        return delivered

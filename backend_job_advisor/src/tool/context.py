"""Agent 工具运行时上下文：注入仓储与当前用户，避免工具函数依赖全局状态。"""

from __future__ import annotations

from dataclasses import dataclass

from config.notify_sse_hub import NotifySseHub
from storage.job_storage import JobStorage
from storage.resume_storage import ResumeStorage


@dataclass(slots=True)
class AdvisorToolContext:
    """与单次对话 / 子任务绑定的只读依赖（由上层在构造工具前填入）。"""

    user_id: str
    job_storage: JobStorage
    resume_storage: ResumeStorage
    notify_sse_hub: NotifySseHub

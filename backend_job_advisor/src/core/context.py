"""流水线运行时依赖包：由 FastAPI lifespan / ``Depends`` 组装后注入 ``AdvisorPipeline``。"""

from __future__ import annotations

from dataclasses import dataclass

from agent.ports import SubTaskPort, TaskLifecyclePort, ToolResultCachePort
from config.notify_sse_hub import NotifySseHub
from service.fact_service import FactService
from service.llm_service import LlmService
from storage.dialogue_history_storage import DialogueHistoryStorage
from storage.job_storage import JobStorage
from storage.resume_storage import ResumeStorage


@dataclass(slots=True)
class AdvisorPipelineDeps:
    """单轮 / 流式对话编排所需的已连接资源（设计文档 §3、§7、§8、§9）。"""

    llm_service: LlmService
    dialogue_history_storage: DialogueHistoryStorage
    fact_service: FactService
    job_storage: JobStorage
    resume_storage: ResumeStorage
    notify_sse_hub: NotifySseHub
    task_port: TaskLifecyclePort | None = None
    sub_task_port: SubTaskPort | None = None
    tool_cache: ToolResultCachePort | None = None

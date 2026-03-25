"""Agent 依赖端口：Mongo tasks/sub_tasks、工具结果缓存等尚未落地时的扩展面（设计文档 §6 / §9 / §10）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from entity.mongo.sub_task import SubTask
from entity.mongo.task import Task


@runtime_checkable
class TaskLifecyclePort(Protocol):
    """主任务读写：Triage 选任务、关闭扫描、新建任务。"""

    async def list_candidate_tasks(
        self,
        user_id: str,
        *,
        created_after: datetime,
        limit: int = 20,
    ) -> list[Task]:
        """返回 ``created_after`` 之后创建的活跃任务，新在前。"""

    async def create_task(self, task: Task) -> str:
        """插入 ``tasks``，返回 ``task.id``。"""


@runtime_checkable
class SubTaskPort(Protocol):
    """子任务读写：Plan 列出未完成子任务、落库 slot / clarify / fact_confirm。"""

    async def list_sub_tasks_by_task(self, task_id: str) -> list[SubTask]:
        """返回指定主任务下已持久化的子任务（含 ``tool_name`` / ``params``）。"""

    async def list_open_sub_tasks(self, task_id: str) -> list[SubTask]:
        """``status`` 为 ``created`` 或 ``waiting`` 的子任务。"""

    async def get_sub_task(self, task_id: str, sub_task_id: str) -> SubTask | None: ...

    async def count_open_clarifies(self, task_id: str) -> int: ...

    async def insert_sub_task(self, sub: SubTask) -> str: ...

    async def update_sub_task_fields(
        self,
        task_id: str,
        sub_task_id: str,
        *,
        set_fields: dict[str, Any],
    ) -> bool: ...

    async def set_sub_task_status(self, task_id: str, sub_task_id: str, status: str) -> bool: ...


# 兼容旧名
SubTaskReadPort = SubTaskPort


@runtime_checkable
class ToolResultCachePort(Protocol):
    """Review / Executor：可缓存工具结果,键建议含 task_id + sub_task_id。"""

    async def get(self, key: str) -> Any | None: ...

    async def set(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None: ...

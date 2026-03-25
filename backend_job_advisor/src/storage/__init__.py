"""存储访问层与后端客户端导出。

保持 ``from storage import Xxx`` 兼容，但避免包导入时立即加载全部子模块，
以减少启动期循环导入风险。
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "ChromaDb",
    "DialogueHistoryStorage",
    "ElasticsearchDb",
    "FactEsStorage",
    "FactVectorStorage",
    "JobStorage",
    "MongoDb",
    "RedisDb",
    "ResumeStorage",
    "SubTaskStorage",
    "TaskStorage",
    "ToolResultCacheStorage",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "ChromaDb": ("config.db.chroma_backend", "ChromaDb"),
    "ElasticsearchDb": ("config.db.elasticsearch_backend", "ElasticsearchDb"),
    "MongoDb": ("config.db.mongo_backend", "MongoDb"),
    "RedisDb": ("config.db.redis_backend", "RedisDb"),
    "DialogueHistoryStorage": (
        "storage.dialogue_history_storage",
        "DialogueHistoryStorage",
    ),
    "FactEsStorage": ("storage.fact_es", "FactEsStorage"),
    "FactVectorStorage": ("storage.fact_vector", "FactVectorStorage"),
    "JobStorage": ("storage.job_storage", "JobStorage"),
    "ResumeStorage": ("storage.resume_storage", "ResumeStorage"),
    "SubTaskStorage": ("storage.sub_task_storage", "SubTaskStorage"),
    "TaskStorage": ("storage.task_storage", "TaskStorage"),
    "ToolResultCacheStorage": (
        "storage.tool_result_cache_storage",
        "ToolResultCacheStorage",
    ),
}


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'storage' has no attribute '{name}'")
    module_path, symbol = target
    module = import_module(module_path)
    value = getattr(module, symbol)
    globals()[name] = value
    return value

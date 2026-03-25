"""核心编排导出。

避免在 ``import core.xxx`` 时触发 ``core.__init__`` 的深层导入链。
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "AdvisorPipeline",
    "AdvisorPipelineDeps",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "AdvisorPipeline": ("core.pipeline", "AdvisorPipeline"),
    "AdvisorPipelineDeps": ("core.context", "AdvisorPipelineDeps"),
}


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'core' has no attribute '{name}'")
    module_path, symbol = target
    module = import_module(module_path)
    value = getattr(module, symbol)
    globals()[name] = value
    return value

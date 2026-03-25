from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "FactService",
    "JobService",
    "LlmService",
    "ResumeService",
    "get_fact_service",
    "get_job_service",
    "get_llm_service",
    "get_resume_service",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "FactService": ("service.fact_service", "FactService"),
    "get_fact_service": ("service.fact_service", "get_fact_service"),
    "JobService": ("service.job_service", "JobService"),
    "get_job_service": ("service.job_service", "get_job_service"),
    "LlmService": ("service.llm_service", "LlmService"),
    "get_llm_service": ("service.llm_service", "get_llm_service"),
    "ResumeService": ("service.resume_service", "ResumeService"),
    "get_resume_service": ("service.resume_service", "get_resume_service"),
}


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'service' has no attribute '{name}'")
    module_path, symbol = target
    module = import_module(module_path)
    value = getattr(module, symbol)
    globals()[name] = value
    return value

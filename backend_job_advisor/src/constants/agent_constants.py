"""与设计文档一致的时间窗与编排常量（§6.1 关闭规则、§9.2 Triage）。"""

from __future__ import annotations


class AgentConstants:
    # Triage：候选主任务「创建时间」窗口（分钟），文档 §9.2
    TRIAGE_CANDIDATE_TASK_MAX_AGE_MINUTES = 30

    # 主任务关闭：最后子任务距今（分钟），文档 §9.3
    TASK_CLOSE_IDLE_AFTER_LAST_SUBTASK_MINUTES = 30

    # 主任务关闭：主任务创建距今（小时），文档 §9.3
    TASK_CLOSE_MAX_AGE_HOURS = 2

    # Executor / Plan 侧拉 Redis 对话条数上限（实现可调）
    DEFAULT_DIALOGUE_HISTORY_LIMIT = 50

    # Plan / Executor 混合检索默认条数
    DEFAULT_FACT_ES_LIMIT = 8
    DEFAULT_FACT_CHROMA_LIMIT = 8
    DEFAULT_FACT_MERGE_LIMIT = 12

    # Plan：同一主任务下处于 created/waiting 的澄清子任务上限
    PLAN_MAX_OPEN_CLARIFY_SUB_TASKS = 5

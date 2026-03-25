from enum import StrEnum


class FactPredicateEnum(StrEnum):
    """事实谓词（键）枚举。"""

    CONSTRAINT_TIME = "constraint_time"  # 时间约束（到岗时间/可面试时间等）
    BEHAVIOR_APPLY = "behavior_apply"  # 求职投递行为
    BEHAVIOR_VIEW = "behavior_view"  # 职位浏览行为

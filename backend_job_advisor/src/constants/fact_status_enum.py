from enum import StrEnum


class FactStatusEnum(StrEnum):
    """事实生命周期状态。"""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"

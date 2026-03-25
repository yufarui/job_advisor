from enum import Enum


class UserJobStatusEnum(str, Enum):
    """用户侧职位状态"""

    saved = "saved"
    viewed = "viewed"
    applied = "applied"
    interviewing = "interviewing"
    offer = "offer"
    rejected = "rejected"
    ignored = "ignored"
    archived = "archived"

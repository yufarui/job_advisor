from enum import IntEnum


class AttentionLevelEnum(IntEnum):
    """关注程度 1–5（整型，与文档约定一致）。"""

    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3
    LEVEL_4 = 4
    LEVEL_5 = 5

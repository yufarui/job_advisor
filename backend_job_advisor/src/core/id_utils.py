"""ID 生成工具。"""

from __future__ import annotations

import secrets
import string

_ID_ALPHABET = string.ascii_lowercase + string.digits
_ID_LEN = 16


def generate_short_id() -> str:
    """生成 16 位短 ID（小写字母+数字）。"""
    return "".join(secrets.choice(_ID_ALPHABET) for _ in range(_ID_LEN))

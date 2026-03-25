from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def now_shanghai() -> datetime:
    """Return current time in Asia/Shanghai timezone."""
    return datetime.now(SHANGHAI_TZ)


def today_range_shanghai() -> tuple[datetime, datetime]:
    """Return [start, end) datetime range for today's Shanghai date."""
    now = now_shanghai()
    start = datetime(now.year, now.month, now.day, tzinfo=SHANGHAI_TZ)
    end = start + timedelta(days=1)
    return start, end

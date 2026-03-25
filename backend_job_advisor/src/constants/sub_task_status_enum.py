from enum import Enum


class SubTaskStatusEnum(str, Enum):
    created = "created"
    waiting = "waiting"
    running = "running"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"

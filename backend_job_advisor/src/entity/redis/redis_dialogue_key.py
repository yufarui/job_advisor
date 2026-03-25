"""Redis 对话 key 的拼装规则。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RedisDialogueKey(BaseModel):
    """由 user_id 与 task_id 生成对话缓存 key。"""

    model_config = ConfigDict(frozen=True, extra="ignore")

    user_id: str = Field(description="用户 ID")
    task_id: str = Field(description="主任务 ID")

    def legacy_key(self) -> str:
        """历史格式 user:{user_id}_{task_id}。"""
        return f"user:{self.user_id}_{self.task_id}"

    def scoped_key(self) -> str:
        """推荐格式，减少下划线歧义。"""
        return f"user:{self.user_id}:task:{self.task_id}"

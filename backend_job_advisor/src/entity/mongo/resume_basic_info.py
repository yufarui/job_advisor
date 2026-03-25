"""简历嵌套对象：基本信息（联系方式与年龄等）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResumeBasicInfo(BaseModel):
    """简历基本信息；性别等以字符串存储（Mongo 不使用枚举类型）。"""

    model_config = ConfigDict(extra="ignore")

    age: int | None = Field(default=None, description="年龄（周岁）")
    email: str | None = Field(default=None, description="电子邮箱")
    phone: str | None = Field(default=None, description="手机号码")
    gender: Literal["male", "female", "other", "unspecified"] | None = Field(
        default=None,
        description="性别取值（字面量四选一）",
    )

    @model_validator(mode="before")
    @classmethod
    def strip_empty_strings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: (None if v == "" else v) for k, v in data.items()}
        return data

"""OpenAI / LangChain 相关配置：先于 ``BaseSettings`` 解析加载 ``.env``。"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_ENV_FILE)


class LlmSettings(BaseSettings):
    """与 ``langchain-openai`` 对齐的 LLM 与 Embedding 模型配置。"""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = Field(
        ...,
        description="OpenAI API Key（或兼容服务的密钥）",
    )
    openai_base_url: str | None = Field(
        default=None,
        description="可选；自建网关或 Azure 兼容端点",
    )
    openai_llm_model: str = Field(
        default="gpt-4o-mini",
        description="对话 / 工具调用用聊天模型",
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        description="事实向量写入与检索共用，须与既有 Chroma 索引维度一致或重建集合",
    )
    openai_llm_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
    )

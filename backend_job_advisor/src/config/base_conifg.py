from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """应用与四类存储连接配置（与设计文档、.env.example 对齐）。"""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="local", description="运行环境标记")

    api_port: int = Field(
        default=8001,
        description="HTTP API 监听端口；须与 CHROMA_PORT 不同，避免 Chroma 客户端误连到本服务",
    )

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "job_advisor"

    redis_url: str = "redis://localhost:6379/0"

    elasticsearch_url: str = "http://localhost:9200"
    es_index_facts: str = "job_advisor_facts"
    es_index_jobs: str = "job_advisor_jobs"

    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_facts_collection: str = "job_advisor_facts"

    dialogue_ttl_seconds: int = Field(
        default=7200,
        description="Redis 短期对话 TTL（秒），设计文档 §7 为 2 小时",
    )

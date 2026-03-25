"""FastAPI Depends 工厂：从 app.state 取已在 lifespan 中创建的单例，再组装服务。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from config.notify_sse_hub import NotifySseHub

if TYPE_CHECKING:
    from config.db.chroma_backend import ChromaDb
    from config.db.elasticsearch_backend import ElasticsearchDb
    from config.db.mongo_backend import MongoDb
    from config.db.redis_backend import RedisDb
    from storage.dialogue_history_storage import DialogueHistoryStorage


def get_mongo_db(request: Request) -> MongoDb:
    return request.app.state.mongo_db


def get_redis_db(request: Request) -> RedisDb:
    return request.app.state.redis_db


def get_dialogue_history_storage(request: Request) -> DialogueHistoryStorage:
    return request.app.state.dialogue_history_storage


def get_elasticsearch_db(request: Request) -> ElasticsearchDb:
    return request.app.state.elasticsearch_db


def get_chroma_db(request: Request) -> ChromaDb:
    return request.app.state.chroma_db


def get_llm(request: Request) -> ChatOpenAI:
    return request.app.state.llm


def get_openai_embeddings(request: Request) -> OpenAIEmbeddings:
    return request.app.state.openai_embeddings


def get_notify_sse_hub(request: Request) -> NotifySseHub:
    return request.app.state.notify_sse_hub


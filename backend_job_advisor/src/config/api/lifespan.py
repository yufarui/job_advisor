from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from config.base_conifg import Settings
from config.llm_config import LlmSettings
from llm import setup_openai_stack
from config.notify_sse_hub import NotifySseHub
from storage import (
    ChromaDb,
    DialogueHistoryStorage,
    ElasticsearchDb,
    MongoDb,
    RedisDb,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    llm_settings = LlmSettings()
    llm, openai_embeddings = setup_openai_stack(llm_settings)
    mongo_db = MongoDb(settings)
    redis_db = RedisDb(settings)
    es_db = ElasticsearchDb(settings)
    chroma_db = ChromaDb(settings)
    await mongo_db.connect()
    await redis_db.connect()
    await es_db.connect()
    chroma_db.connect()

    dialogue_history_storage = DialogueHistoryStorage(
        redis_db,
        ttl_seconds=3600,
        max_messages=10,
        mongo=mongo_db,
    )
    notify_sse_hub = NotifySseHub()

    app.state.mongo_db = mongo_db
    app.state.redis_db = redis_db
    app.state.dialogue_history_storage = dialogue_history_storage
    app.state.elasticsearch_db = es_db
    app.state.chroma_db = chroma_db
    app.state.llm = llm
    app.state.openai_embeddings = openai_embeddings
    app.state.notify_sse_hub = notify_sse_hub

    try:
        yield
    finally:
        await es_db.aclose()
        await redis_db.aclose()
        chroma_db.close()
        await mongo_db.close()


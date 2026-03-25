"""路由层：通过 Depends(工厂函数) 注入服务（与手写组合根 lifespan 配合）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from api.chat_api import router as chat_router
from api.fact_api import router as fact_router
from api.job_api import router as job_router, router_user_jobs
from api.notify_api import router as notify_router
from api.resume_api import router as resume_router
from config.api.request_factory import (
    get_chroma_db,
    get_elasticsearch_db,
    get_mongo_db,
    get_redis_db,
)
from storage import ChromaDb, ElasticsearchDb, MongoDb, RedisDb

router = APIRouter(tags=["di-demo"])
router.include_router(chat_router)
router.include_router(job_router)
router.include_router(router_user_jobs)
router.include_router(resume_router)
router.include_router(fact_router)
router.include_router(notify_router)


@router.get("/deps/ping")
async def deps_ping(
    mongo: Annotated[MongoDb, Depends(get_mongo_db)],
    redis: Annotated[RedisDb, Depends(get_redis_db)],
    es: Annotated[ElasticsearchDb, Depends(get_elasticsearch_db)],
    chroma: Annotated[ChromaDb, Depends(get_chroma_db)],
) -> dict[str, str]:
    await mongo.database.command("ping")
    await redis.client.ping()
    await es.client.ping()
    chroma.client.heartbeat()
    return {"status": "ok"}

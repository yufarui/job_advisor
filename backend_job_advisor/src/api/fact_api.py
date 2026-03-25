"""用户事实：Elasticsearch + Chroma；入参出参与 ``entity.view`` 对齐。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from entity.view.fact_api_models import (
    BackendFactUpsertRequest,
    BackendFactUpsertResponse,
    FactBulkInsertRequest,
    FactBulkInsertResponse,
    FactDialogueSearchRequest,
    UserFactListResponse,
)
from entity.view.user_fact_update_request import FactUpdateResponse, UserFactUpdateRequest
from entity.view.user_fact_view import UserFactView
from service.fact_service import FactService, get_fact_service

FactServiceDep = Annotated[FactService, Depends(get_fact_service)]

router = APIRouter(prefix="/facts", tags=["facts"])


@router.get("/user/{user_id}/list", response_model=UserFactListResponse)
async def get_facts_for_user(
    user_id: str,
    svc: FactServiceDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> UserFactListResponse:
    """页面：仅从 ES 拉取当前用户全部事实。"""
    facts = await svc.list_user_facts(user_id, limit=limit)
    return UserFactListResponse(facts=facts)


@router.post(
    "/user/{user_id}/search",
    response_model=UserFactListResponse,
)
async def post_search_facts_by_dialogue(
    user_id: str,
    body: FactDialogueSearchRequest,
    svc: FactServiceDep,
) -> UserFactListResponse:
    """按对话检索：ES ``multi_match``（BM25）+ Chroma 向量，结果合并去重。"""
    facts = await svc.search_facts_by_dialogue(
        user_id,
        body.dialogue,
        es_limit=body.es_limit,
        chroma_limit=body.chroma_limit,
        merge_limit=body.merge_limit,
    )
    return UserFactListResponse(facts=facts)


@router.get(
    "/user/{user_id}/fact/{fact_no}/detail",
    response_model=UserFactView,
)
async def get_fact_detail(
    user_id: str,
    fact_no: str,
    svc: FactServiceDep,
) -> UserFactView:
    view = await svc.get_fact_view(user_id, fact_no)
    if view is None:
        raise HTTPException(status_code=404, detail="fact not found")
    return view


@router.post("/user/{user_id}/bulk", response_model=FactBulkInsertResponse)
async def post_facts_page_bulk(
    user_id: str,
    body: FactBulkInsertRequest,
    svc: FactServiceDep,
) -> FactBulkInsertResponse | JSONResponse:
    """页面：批量新增；先按 ``fact_no`` 查 ES 去重，再写 ES + Chroma。"""
    if not body.facts:
        raise HTTPException(status_code=400, detail="facts must not be empty")
    result = await svc.add_facts_for_page(user_id, body.facts)
    if not result.ok:
        if result.duplicates:
            return JSONResponse(
                status_code=409,
                content=result.model_dump(mode="json"),
            )
        if result.reason == "user_id_mismatch":
            raise HTTPException(status_code=403, detail=result.reason)
        raise HTTPException(status_code=400, detail=result.reason or "invalid request")
    return FactBulkInsertResponse(
        inserted_fact_nos=result.inserted_fact_nos,
        count=len(result.inserted_fact_nos),
    )


@router.post("/bulk", response_model=FactBulkInsertResponse)
async def post_facts_bulk_same_user(
    body: FactBulkInsertRequest,
    svc: FactServiceDep,
) -> FactBulkInsertResponse | JSONResponse:
    """页面批量新增（兼容）：请求体内所有 ``Fact.user_id`` 须一致。"""
    if not body.facts:
        raise HTTPException(status_code=400, detail="facts must not be empty")
    uids = {f.user_id for f in body.facts}
    if len(uids) != 1:
        raise HTTPException(status_code=400, detail="all facts must share the same user_id")
    user_id = next(iter(uids))
    result = await svc.add_facts_for_page(user_id, body.facts)
    if not result.ok:
        if result.duplicates:
            return JSONResponse(
                status_code=409,
                content=result.model_dump(mode="json"),
            )
        if result.reason == "user_id_mismatch":
            raise HTTPException(status_code=403, detail=result.reason)
        raise HTTPException(status_code=400, detail=result.reason or "invalid request")
    return FactBulkInsertResponse(
        inserted_fact_nos=result.inserted_fact_nos,
        count=len(result.inserted_fact_nos),
    )


@router.post("/backend/upsert", response_model=BackendFactUpsertResponse)
async def post_facts_backend_upsert(
    body: BackendFactUpsertRequest,
    svc: FactServiceDep,
) -> BackendFactUpsertResponse:
    """后端管道：无 ``fact_no`` 插入、有 ``fact_no`` 合并更新；可选 ``ignore_duplicate``。"""
    if not body.facts:
        return BackendFactUpsertResponse(success=True)
    return await svc.upsert_facts_backend(
        body.facts,
        ignore_duplicate=body.ignore_duplicate,
    )


@router.patch("/update", response_model=FactUpdateResponse)
async def patch_fact_update(
    body: UserFactUpdateRequest,
    svc: FactServiceDep,
) -> FactUpdateResponse:
    """页面：按主键 PATCH，同步 ES + Chroma。"""
    ok = await svc.update_fact(body)
    if not ok:
        raise HTTPException(status_code=404, detail="fact not found or no change")
    return FactUpdateResponse()

"""用户事实应用服务：编排 ES（权威存储）与 Chroma（向量），对外暴露页面与后端用例。

职责边界：
- **FactEsStorage / FactVectorStorage**：纯存储访问
- **FactService**：校验、去重策略、双写顺序、结果合并与视图转换
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import Depends

from config.api.request_factory import get_chroma_db, get_elasticsearch_db
from config.log_config import log_io
from entity.domain.fact_domain import Fact
from entity.view.fact_api_models import (
    BackendFactUpsertResponse,
    FactPageBulkAddResult,
)
from entity.view.user_fact_update_request import UserFactUpdateRequest
from entity.view.user_fact_view import UserFactView
from core.time_utils import now_shanghai
from storage import ChromaDb, ElasticsearchDb
from service.llm_service import LlmService, get_llm_service
from storage.fact_es import FactEsStorage
from storage.fact_vector import FactVectorStorage

logger = logging.getLogger(__name__)


# --- 领域小工具（无 I/O）---


def _is_new_fact(f: Fact) -> bool:
    return not f.fact_no or not str(f.fact_no).strip()


def _merge_fact_with_existing(existing: Fact, incoming: Fact) -> Fact:
    """后端合并更新：仅覆盖请求体中出现的字段，保留 ``created_at`` 与 ``fact_no``。"""
    patch = incoming.model_dump(exclude_unset=True)
    patch.pop("fact_no", None)
    merged = existing.model_copy(update=patch)
    merged = merged.model_copy(
        update={
            "fact_no": existing.fact_no,
            "created_at": existing.created_at,
        }
    )
    return Fact.model_validate(merged.model_dump(mode="python"))


def _facts_to_views(facts: list[Fact]) -> list[UserFactView]:
    return [UserFactView.model_validate(f.model_dump(mode="python")) for f in facts]


def _merge_dialogue_search_results(
    es_facts: list[Fact],
    chroma_facts: list[Fact],
    *,
    merge_limit: int,
) -> list[Fact]:
    """ES 结果优先，再追加 Chroma 独有 ``fact_no``，按 ``fact_no`` 去重。"""
    seen: set[str] = set()
    merged: list[Fact] = []
    for f in es_facts:
        fn = f.fact_no and str(f.fact_no).strip()
        if fn and fn not in seen:
            seen.add(fn)
            merged.append(f)
    for f in chroma_facts:
        fn = f.fact_no and str(f.fact_no).strip()
        if fn and fn not in seen:
            seen.add(fn)
            merged.append(f)
    cap = max(1, min(merge_limit, 200))
    return merged[:cap]


class FactService:
    def __init__(
        self,
        es: ElasticsearchDb,
        chroma: ChromaDb,
        llm_service: LlmService,
    ) -> None:
        self._es_store = FactEsStorage(es)
        self._vec_store = FactVectorStorage(chroma, llm_service.embeddings)

    # --- 查询（以 ES 为真源）---

    @log_io
    async def list_user_facts(
        self, user_id: str, *, limit: int = 200
    ) -> list[UserFactView]:
        facts = await self._es_store.list_facts_by_user_id(user_id, limit=limit)
        logger.debug("list_user_facts user_id=%s count=%s", user_id, len(facts))
        return _facts_to_views(facts)

    @log_io
    async def get_fact_view(
        self, user_id: str, fact_no: str
    ) -> UserFactView | None:
        f = await self._es_store.get_fact_by_fact_no(fact_no)
        if f is None or f.user_id != user_id:
            return None
        return UserFactView.model_validate(f.model_dump(mode="python"))

    @log_io
    async def search_facts_by_dialogue(
        self,
        user_id: str,
        dialogue: str,
        *,
        es_limit: int = 5,
        chroma_limit: int = 5,
        merge_limit: int = 5,
    ) -> list[UserFactView]:
        text = dialogue.strip()
        if not text:
            return []

        es_facts = await self._es_store.search_bm25_by_dialogue(
            user_id, text, limit=es_limit
        )
        chroma_fact_nos = await self._vec_store.query_fact_nos_by_dialogue(
            user_id, text, n_results=chroma_limit
        )

        chroma_facts: list[Fact] = []
        for fn in chroma_fact_nos:
            f = await self._es_store.get_fact_by_fact_no(fn)
            if f is not None and f.user_id == user_id:
                chroma_facts.append(f)

        merged = _merge_dialogue_search_results(
            es_facts, chroma_facts, merge_limit=merge_limit
        )
        logger.info(
            "search_facts_by_dialogue user_id=%s es_hits=%s chroma_nos=%s merged=%s",
            user_id,
            len(es_facts),
            len(chroma_fact_nos),
            len(merged),
        )
        return _facts_to_views(merged)

    # --- 页面写路径 ---

    @log_io
    async def update_fact(self, body: UserFactUpdateRequest) -> bool:
        ok = await self._es_store.update_fact(body)
        if not ok:
            return False
        updated = await self._es_store.get_fact_by_fact_no(body.fact_no)
        if updated and updated.fact_no:
            await self._vec_store.upsert_facts([updated])
        logger.info(
            "update_fact fact_no=%s chroma_upserted=%s", body.fact_no, bool(updated)
        )
        return True

    @log_io
    async def add_facts_for_page(
        self, user_id: str, facts: list[Fact]
    ) -> FactPageBulkAddResult:
        if not facts:
            return FactPageBulkAddResult(ok=True, inserted_fact_nos=[])

        if any(not _is_new_fact(f) for f in facts):
            logger.info(
                "add_facts_for_page rejected: facts must omit fact_no user_id=%s", user_id
            )
            return FactPageBulkAddResult(
                ok=False,
                reason="facts_must_be_insert_without_fact_no",
                duplicates=[],
                inserted_fact_nos=[],
            )
        if any(f.user_id != user_id for f in facts):
            logger.warning("add_facts_for_page user_id_mismatch path=%s", user_id)
            return FactPageBulkAddResult(
                ok=False,
                reason="user_id_mismatch",
                duplicates=[],
                inserted_fact_nos=[],
            )

        keys = [(f.user_id, str(f.predicate)) for f in facts]
        if len(keys) != len(set(keys)):
            return FactPageBulkAddResult(
                ok=False,
                reason="duplicate_predicate_in_batch",
                duplicates=[],
                inserted_fact_nos=[],
            )

        dup_rows = await self._collect_duplicates_for_new_facts(facts)
        if dup_rows:
            logger.info(
                "add_facts_for_page duplicate_predicate user_id=%s dup_count=%s",
                user_id,
                len(dup_rows),
            )
            return FactPageBulkAddResult(
                ok=False,
                reason="duplicate_predicate",
                duplicates=_facts_to_views(dup_rows),
                inserted_fact_nos=[],
            )

        now = now_shanghai()
        prepared = [
            f if f.created_at is not None else f.model_copy(update={"created_at": now})
            for f in facts
        ]
        stored = await self._es_store.insert_facts(prepared)
        with_fn = [f for f in stored if f.fact_no and str(f.fact_no).strip()]
        if with_fn:
            await self._vec_store.upsert_facts(with_fn)
        nos = [str(f.fact_no) for f in stored if f.fact_no]
        logger.info(
            "add_facts_for_page success user_id=%s inserted=%s",
            user_id,
            len(nos),
        )
        return FactPageBulkAddResult(ok=True, duplicates=[], inserted_fact_nos=nos)

    async def _collect_duplicates_for_new_facts(self, facts: list[Fact]) -> list[Fact]:
        """同一 ``user_id`` + ``predicate`` 已存在任意文档则视为冲突。"""
        out: list[Fact] = []
        seen_fn: set[str] = set()
        for f in facts:
            pred = str(f.predicate)
            for h in await self._es_store.list_by_user_and_predicate(
                f.user_id, pred, limit=50
            ):
                fn = h.fact_no and str(h.fact_no).strip()
                if fn and fn not in seen_fn:
                    seen_fn.add(fn)
                    out.append(h)
        return out

    # --- 后端写路径 ---

    async def _collect_duplicates_for_backend_batch(self, facts: list[Fact]) -> list[Fact]:
        out: list[Fact] = []
        seen_fn: set[str] = set()
        for f in facts:
            if _is_new_fact(f):
                pred = str(f.predicate)
                hits = await self._es_store.list_by_user_and_predicate(
                    f.user_id, pred, limit=50
                )
            else:
                fn = str(f.fact_no).strip()
                ex = await self._es_store.get_fact_by_fact_no(fn)
                if ex is None or ex.user_id != f.user_id:
                    continue
                merged = _merge_fact_with_existing(ex, f)
                pred = str(merged.predicate)
                hits = await self._es_store.list_by_user_and_predicate(
                    merged.user_id, pred, limit=50
                )
                mfn = merged.fact_no and str(merged.fact_no).strip()
                hits = [h for h in hits if (h.fact_no or "") != mfn]

            for h in hits:
                hfn = h.fact_no and str(h.fact_no).strip()
                if hfn and hfn not in seen_fn:
                    seen_fn.add(hfn)
                    out.append(h)
        return out

    async def _apply_backend_writes(
        self,
        facts: list[Fact],
        *,
        now: datetime,
    ) -> tuple[list[str], list[str], list[str], list[Fact]]:
        inserted: list[str] = []
        updated: list[str] = []
        errors: list[str] = []
        to_vec: list[Fact] = []
        new_batch: list[Fact] = []

        for f in facts:
            if _is_new_fact(f):
                new_batch.append(
                    f
                    if f.created_at is not None
                    else f.model_copy(update={"created_at": now})
                )
                continue

            fn = str(f.fact_no).strip()
            ex = await self._es_store.get_fact_by_fact_no(fn)
            if ex is None:
                errors.append(f"fact_no not found: {fn}")
                continue
            if ex.user_id != f.user_id:
                errors.append(f"user_id mismatch for fact_no {fn}")
                continue
            merged = _merge_fact_with_existing(ex, f)
            if await self._es_store.index_replace_fact(merged):
                updated.append(fn)
                to_vec.append(merged)
            else:
                errors.append(f"es replace failed: {fn}")

        if new_batch:
            stored = await self._es_store.insert_facts(new_batch)
            for sf in stored:
                if sf.fact_no and str(sf.fact_no).strip():
                    inserted.append(str(sf.fact_no))
                    to_vec.append(sf)

        return inserted, updated, errors, to_vec

    @log_io
    async def upsert_facts_backend(
        self,
        facts: list[Fact],
        *,
        ignore_duplicate: bool = False,
    ) -> BackendFactUpsertResponse:
        if not facts:
            return BackendFactUpsertResponse(success=True)

        if not ignore_duplicate:
            dup_rows = await self._collect_duplicates_for_backend_batch(facts)
            if dup_rows:
                logger.info(
                    "upsert_facts_backend blocked by duplicates count=%s",
                    len(dup_rows),
                )
                return BackendFactUpsertResponse(
                    success=False,
                    duplicate_facts=_facts_to_views(dup_rows),
                )

        now = now_shanghai()
        inserted, updated, errors, to_vec = await self._apply_backend_writes(
            facts, now=now
        )

        if to_vec:
            await self._vec_store.upsert_facts(
                [x for x in to_vec if x.fact_no and str(x.fact_no).strip()]
            )

        success = not errors
        logger.info(
            "upsert_facts_backend success=%s inserted=%s updated=%s errors=%s ignore_dup=%s",
            success,
            len(inserted),
            len(updated),
            len(errors),
            ignore_duplicate,
        )
        return BackendFactUpsertResponse(
            success=success,
            inserted_fact_nos=inserted,
            updated_fact_nos=updated,
            errors=errors,
        )


def get_fact_service(
    es: ElasticsearchDb = Depends(get_elasticsearch_db),
    chroma: ChromaDb = Depends(get_chroma_db),
    llm_service: LlmService = Depends(get_llm_service),
) -> FactService:
    return FactService(es, chroma, llm_service)

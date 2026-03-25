"""事实的 Chroma 向量仓储：与 ES ``_id``（即 ``fact_no``）共用 id，便于双写与对账。

职责边界：
- 同步阻塞的 Chroma HTTP 调用经 ``asyncio.to_thread`` 暴露为 async API
- 不写业务规则（去重、合并等由 Service 处理）
"""

from __future__ import annotations

import asyncio
import logging

from chromadb.api.models.Collection import Collection
from langchain_openai import OpenAIEmbeddings

from config.db.chroma_backend import ChromaDb
from config.log_config import log_io
from entity.domain.fact_domain import Fact

logger = logging.getLogger(__name__)

_MAX_QUERY_RESULTS = 100


class FactVectorStorage:
    """单 collection（``ChromaDb.facts_collection``）上的 upsert / 检索 / 删除。

    向量由注入的 ``OpenAIEmbeddings`` 生成；若集合曾用 Chroma 内置模型建索引，需换集合名或全量重灌。
    """

    def __init__(self, chroma: ChromaDb, embeddings: OpenAIEmbeddings) -> None:
        self._chroma = chroma
        self._embeddings = embeddings
        self._collection_name = chroma.facts_collection
        self._collection: Collection | None = None

    def _get_collection(self) -> Collection:
        if self._collection is None:
            self._collection = self._chroma.client.get_or_create_collection(
                name=self._collection_name,
            )
            logger.debug("Chroma collection ready name=%s", self._collection_name)
        return self._collection

    def _facts_to_chroma_batch(
        self, facts: list[Fact]
    ) -> tuple[list[str], list[str], list[dict[str, str | int | float]]]:
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, str | int | float]] = []
        for fact in facts:
            if not fact.fact_no or not str(fact.fact_no).strip():
                continue
            ids.append(fact.to_chroma_id())
            documents.append(fact.to_chroma_document())
            metadatas.append(fact.to_chroma_metadata())
        return ids, documents, metadatas

    def _upsert_sync(self, facts: list[Fact]) -> None:
        ids, documents, metadatas = self._facts_to_chroma_batch(facts)
        if not ids:
            logger.debug("Chroma upsert skipped: no facts with fact_no")
            return
        vectors = self._embeddings.embed_documents(documents)
        coll = self._get_collection()
        coll.upsert(
            ids=ids,
            embeddings=vectors,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info("Chroma upsert count=%s collection=%s", len(ids), self._collection_name)

    @log_io
    async def upsert_facts(self, facts: list[Fact]) -> None:
        """幂等写入；每条须已有非空 ``fact_no``。"""
        if not facts:
            return
        await asyncio.to_thread(self._upsert_sync, facts)

    def _query_fact_nos_sync(self, dialogue: str, user_id: str, n_results: int) -> list[str]:
        q = dialogue.strip()
        if not q:
            return []
        n = max(1, min(n_results, _MAX_QUERY_RESULTS))
        q_emb = self._embeddings.embed_query(q)
        coll = self._get_collection()
        res = coll.query(
            query_embeddings=[q_emb],
            n_results=n,
            where={"user_id": user_id},
        )
        ids_batch = res.get("ids") or []
        if not ids_batch:
            return []
        first = ids_batch[0]
        out = [str(x) for x in first if x]
        logger.info(
            "Chroma query user_id=%s n_results=%s returned_fact_nos=%s",
            user_id,
            n,
            len(out),
        )
        return out

    @log_io
    async def query_fact_nos_by_dialogue(
        self,
        user_id: str,
        dialogue: str,
        *,
        n_results: int = 20,
    ) -> list[str]:
        """向量检索：返回与 ES ``_id`` 一致的 ``fact_no`` 列表。"""
        return await asyncio.to_thread(
            self._query_fact_nos_sync,
            dialogue,
            user_id,
            n_results,
        )

    def _delete_sync(self, fact_nos: list[str]) -> None:
        if not fact_nos:
            return
        self._get_collection().delete(ids=fact_nos)
        logger.info(
            "Chroma delete count=%s collection=%s",
            len(fact_nos),
            self._collection_name,
        )

    @log_io
    async def delete_by_fact_nos(self, fact_nos: list[str]) -> None:
        await asyncio.to_thread(self._delete_sync, fact_nos)

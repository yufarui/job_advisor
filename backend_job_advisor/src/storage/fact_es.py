"""事实的 Elasticsearch 仓储：仅负责与 ES 的 I/O 与查询 DSL，不含业务编排。

职责边界：
- 读：按 ``fact_no``（即 ``_id``）、按 ``user_id``、按 ``user_id``+``predicate``、BM25 全文检索
- 写：插入（``_id`` = ``fact_no``）、按 ``fact_no`` 覆盖、``update`` 部分字段
"""

from __future__ import annotations

import logging

from elasticsearch import NotFoundError

from config.db.elasticsearch_backend import ElasticsearchDb
from config.log_config import log_io
from entity.domain.fact_domain import Fact
from entity.view.user_fact_update_request import UserFactUpdateRequest

logger = logging.getLogger(__name__)

_MAX_SEARCH_SIZE = 500
_MAX_USER_PREDICATE_QUERY = 100
_MAX_BM25_QUERY = 100


def _hits_to_facts(hits: list[dict]) -> list[Fact]:
    return [Fact.from_es_hit(h) for h in hits]


class FactEsStorage:
    """封装 ``facts_index`` 上的 CRUD 与检索；领域对象统一为 ``Fact``。"""

    def __init__(self, es: ElasticsearchDb) -> None:
        self._es = es
        self._index = es.facts_index

    # ------------------------------------------------------------------ 读
    @log_io
    async def get_fact_by_fact_no(self, fact_no: str) -> Fact | None:
        try:
            resp = await self._es.client.get(index=self._index, id=fact_no)
        except NotFoundError:
            logger.debug("ES get miss index=%s fact_no=%s", self._index, fact_no)
            return None
        body = resp.body
        hit = {"_id": body["_id"], "_source": body.get("_source") or {}}
        return Fact.from_es_hit(hit)

    async def _search_facts(self, query: dict, *, size: int) -> list[Fact]:
        capped = max(1, min(size, _MAX_SEARCH_SIZE))
        resp = await self._es.client.search(index=self._index, query=query, size=capped)
        hits = resp.body.get("hits", {}).get("hits", [])
        facts = _hits_to_facts(hits)
        logger.debug(
            "ES search index=%s size_cap=%s raw_hits=%s",
            self._index,
            capped,
            len(facts),
        )
        return facts

    @log_io
    async def list_by_user_and_predicate(
        self,
        user_id: str,
        predicate: str,
        *,
        limit: int = 50,
    ) -> list[Fact]:
        """同一用户、同一谓词下的文档（用于「每用户每谓词一条」去重）。"""
        size = max(1, min(limit, _MAX_USER_PREDICATE_QUERY))
        return await self._search_facts(
            {
                "bool": {
                    "filter": [
                        {"term": {"user_id": user_id}},
                        {"term": {"predicate": predicate}},
                    ],
                },
            },
            size=size,
        )

    @log_io
    async def list_facts_by_user_id(
        self, user_id: str, *, limit: int = 200
    ) -> list[Fact]:
        size = max(1, min(limit, _MAX_SEARCH_SIZE))
        return await self._search_facts(
            {"term": {"user_id": user_id}},
            size=size,
        )

    @log_io
    async def search_bm25_by_dialogue(
        self,
        user_id: str,
        text: str,
        *,
        limit: int = 20,
    ) -> list[Fact]:
        q = text.strip()
        if not q:
            return []
        size = max(1, min(limit, _MAX_BM25_QUERY))
        facts = await self._search_facts(
            {
                "bool": {
                    "filter": [{"term": {"user_id": user_id}}],
                    "must": [
                        {
                            "multi_match": {
                                "query": q,
                                "fields": ["value^1.5", "content^1.5", "predicate"],
                                "type": "best_fields",
                                "operator": "or",
                            }
                        }
                    ],
                }
            },
            size=size,
        )
        logger.info(
            "ES BM25 dialogue search user_id=%s query_len=%s hits=%s",
            user_id,
            len(q),
            len(facts),
        )
        return facts

    # ------------------------------------------------------------------ 写
    @log_io
    async def insert_facts(self, facts: list[Fact]) -> list[Fact]:
        """``_id`` = ``fact_no``；未提供 ``fact_no`` 时使用 ``user_id:predicate``。"""
        out: list[Fact] = []
        for f in facts:
            fact_no = (f.fact_no or "").strip() or Fact.generate_fact_no(
                f.user_id, f.predicate
            )
            f = f.model_copy(update={"fact_no": fact_no})
            doc_body = f.to_es_doc()
            await self._es.client.index(
                index=self._index,
                id=fact_no,
                document=doc_body,
            )
            out.append(f)
        logger.info("ES insert index=%s count=%s", self._index, len(out))
        return out

    @log_io
    async def index_replace_fact(self, fact: Fact) -> bool:
        if not fact.fact_no or not str(fact.fact_no).strip():
            logger.warning("index_replace_fact skipped: missing fact_no")
            return False
        fn = str(fact.fact_no).strip()
        await self._es.client.index(
            index=self._index,
            id=fn,
            document=fact.to_es_doc(),
        )
        logger.debug("ES index replace fact_no=%s index=%s", fn, self._index)
        return True

    @log_io
    async def update_fact(self, body: UserFactUpdateRequest) -> bool:
        """PATCH：``doc`` 部分更新；``fact_no`` 为文档主键不可通过此接口修改。"""
        existing = await self.get_fact_by_fact_no(body.fact_no)
        if existing is None or existing.user_id != body.user_id:
            logger.debug(
                "ES update_fact aborted: not found or user mismatch fact_no=%s",
                body.fact_no,
            )
            return False
        partial = body.to_elasticsearch_partial()
        if not partial:
            return True
        try:
            await self._es.client.update(
                index=self._index,
                id=body.fact_no,
                doc=partial,
            )
        except NotFoundError:
            logger.warning(
                "ES update NotFound fact_no=%s index=%s", body.fact_no, self._index
            )
            return False
        return True

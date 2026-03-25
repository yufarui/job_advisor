from __future__ import annotations

from elasticsearch import AsyncElasticsearch

from config.base_conifg import Settings


class ElasticsearchDb:
    """组合根里 `es = ElasticsearchDb(settings)`，再 `SomeService(es)`。"""

    def __init__(self, settings: Settings) -> None:
        self.facts_index = settings.es_index_facts
        self._client = AsyncElasticsearch(
            hosts=[settings.elasticsearch_url],
            request_timeout=10,
        )

    @property
    def client(self) -> AsyncElasticsearch:
        return self._client

    async def connect(self) -> None:
        if not await self._client.ping():
            raise RuntimeError("Elasticsearch ping failed")

    async def aclose(self) -> None:
        await self._client.close()

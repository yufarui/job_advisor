from __future__ import annotations

import chromadb
from chromadb.api import ClientAPI

from config.base_conifg import Settings


class ChromaDb:
    """组合根里 `chroma = ChromaDb(settings)`，再 `SomeService(chroma)`。"""

    def __init__(self, settings: Settings) -> None:
        self.facts_collection = settings.chroma_facts_collection
        self._client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )

    @property
    def client(self) -> ClientAPI:
        return self._client

    def connect(self) -> None:
        self._client.heartbeat()

    def close(self) -> None:
        self._client.close()

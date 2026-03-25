"""进程内全局 LLM / Embedding 单例；在 FastAPI lifespan 中安装，与 ``app.state`` 同步。"""

from __future__ import annotations

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

_llm: ChatOpenAI | None = None
_openai_embeddings: OpenAIEmbeddings | None = None


def install_llm_runtime(llm: ChatOpenAI, embeddings: OpenAIEmbeddings) -> None:
    global _llm, _openai_embeddings
    _llm = llm
    _openai_embeddings = embeddings


def get_llm() -> ChatOpenAI:
    if _llm is None:
        raise RuntimeError("LLM 未初始化：请在应用 lifespan 中调用 install_llm_runtime")
    return _llm


def get_openai_embeddings() -> OpenAIEmbeddings:
    if _openai_embeddings is None:
        raise RuntimeError(
            "OpenAI Embeddings 未初始化：请在应用 lifespan 中调用 install_llm_runtime"
        )
    return _openai_embeddings

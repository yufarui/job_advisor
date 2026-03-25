"""LangChain OpenAI：LLM 与 Embedding 工厂及进程内全局访问。"""

from __future__ import annotations

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from config.llm_config import LlmSettings
from llm.clients import build_chat_openai, build_openai_embeddings
from llm.runtime import (
    get_llm,
    get_openai_embeddings,
    install_llm_runtime,
)

__all__ = [
    "build_chat_openai",
    "build_openai_embeddings",
    "get_llm",
    "get_openai_embeddings",
    "install_llm_runtime",
    "setup_openai_stack",
]


def setup_openai_stack(settings: LlmSettings) -> tuple[ChatOpenAI, OpenAIEmbeddings]:
    """构建 LLM 与 Embedding，写入进程全局单例；返回值供挂到 ``app.state``。"""
    llm = build_chat_openai(settings)
    embeddings = build_openai_embeddings(settings)
    install_llm_runtime(llm, embeddings)
    return llm, embeddings

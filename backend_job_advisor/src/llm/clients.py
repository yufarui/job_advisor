"""基于 ``langchain-openai`` 构造 ``ChatOpenAI`` 与 ``OpenAIEmbeddings``。"""

from __future__ import annotations

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from config.llm_config import LlmSettings


def build_chat_openai(settings: LlmSettings) -> ChatOpenAI:
    kwargs: dict = {
        "model": settings.openai_llm_model,
        "api_key": settings.openai_api_key,
        "temperature": settings.openai_llm_temperature,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return ChatOpenAI(**kwargs)


def build_openai_embeddings(settings: LlmSettings) -> OpenAIEmbeddings:
    kwargs: dict = {
        "model": settings.openai_embedding_model,
        "api_key": settings.openai_api_key,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAIEmbeddings(**kwargs)

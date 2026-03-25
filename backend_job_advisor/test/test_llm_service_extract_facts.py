from __future__ import annotations
import asyncio

import pytest

from constants.fact_predicate_enum import FactPredicateEnum
from entity.domain.fact_domain import Fact
from service.llm_service import LlmService, _ExtractedFact, _ExtractedFacts


class _FakeRunnable:
    def __init__(self, output):
        self._output = output

    async def ainvoke(self, _messages):
        return self._output


class _FakeChatModel:
    def __init__(self, output):
        self._output = output

    def bind(self, **_kwargs):
        return self

    def with_structured_output(self, _schema, **_kwargs):
        return _FakeRunnable(self._output)


class _DummyEmbeddings:
    pass


@pytest.mark.asyncio
async def test_extract_facts_from_user_input_empty_input_returns_empty_list():
    svc = LlmService(chat_model=_FakeChatModel(_ExtractedFacts(facts=[])), embeddings=_DummyEmbeddings())

    out = await svc.extract_facts_from_user_input(user_id="u1", user_input="   ")

    assert out == []


@pytest.mark.asyncio
async def test_extract_facts_from_user_input_parses_and_clears_fact_no():
    model_out = _ExtractedFacts(
        facts=[
            _ExtractedFact(
                predicate=FactPredicateEnum.CONSTRAINT_TIME,
                value="一周以内",
                content="我到岗时间为一周以内",
                confidence=0.92,
            )
        ]
    )
    svc = LlmService(chat_model=_FakeChatModel(model_out), embeddings=_DummyEmbeddings())

    out = await svc.extract_facts_from_user_input(user_id="user_dev", user_input="我到岗时间为一周以内")

    assert len(out) == 1
    fact = out[0]
    assert isinstance(fact, Fact)
    assert fact.user_id == "user_dev"
    assert fact.predicate == FactPredicateEnum.CONSTRAINT_TIME
    assert fact.value == "一周以内"
    assert fact.content == "我到岗时间为一周以内"
    # 抽取结果用于 upsert 新增路径，必须清空自动生成的 fact_no
    assert fact.fact_no is None


@pytest.mark.asyncio
async def test_extract_facts_from_user_input_skips_empty_value_and_content():
    model_out = _ExtractedFacts(
        facts=[
            _ExtractedFact(
                predicate=FactPredicateEnum.BEHAVIOR_VIEW,
                value="",
                content="",
                confidence=0.8,
            )
        ]
    )
    svc = LlmService(chat_model=_FakeChatModel(model_out), embeddings=_DummyEmbeddings())

    out = await svc.extract_facts_from_user_input(user_id="u1", user_input="我看了几个职位")

    assert out == []

if __name__ == "__main__":
    pytest.main(["-v", __file__])
    asyncio.run(test_extract_facts_from_user_input_parses_and_clears_fact_no())
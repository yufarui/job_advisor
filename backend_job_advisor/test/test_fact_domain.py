from __future__ import annotations

import pytest

from constants.fact_predicate_enum import FactPredicateEnum
from entity.domain.fact_domain import Fact


# 1) 基础断言：fact_no 由 user_id + predicate 生成
def test_generate_fact_no_basic():
    assert Fact.generate_fact_no("u001", FactPredicateEnum.PREF_ROLE) == "u001:pref_role"


# 2) fixture 用法
def test_generate_fact_no_with_fixture(default_user_id, predicate_pref_role):
    got = Fact.generate_fact_no(default_user_id, predicate_pref_role)
    assert got == "u_demo_001:pref_role"


def test_generate_fact_no_empty_user(empty_user_id, predicate_pref_role):
    with pytest.raises(ValueError):
        Fact.generate_fact_no(empty_user_id, predicate_pref_role)


# 3) parametrize 数据驱动
@pytest.mark.parametrize(
    "user_id, predicate, expected",
    [
        ("uA", "pref_role", "uA:pref_role"),
        ("uB", FactPredicateEnum.PREF_SALARY, "uB:pref_salary"),
        ("u_c", FactPredicateEnum.PROFILE_SKILL, "u_c:profile_skill"),
    ],
)
def test_generate_fact_no_parametrize(user_id, predicate, expected):
    assert Fact.generate_fact_no(user_id, predicate) == expected


# 4) fixture + parametrize 组合
@pytest.mark.parametrize("input_user", ["uA", "uB", "uC"])
def test_generate_fact_no_with_fixture_and_param(default_user_id, input_user):
    uid = input_user or default_user_id
    out = Fact.generate_fact_no(uid, FactPredicateEnum.PREF_ROLE)
    assert out.startswith(uid)
    assert "pref_role" in out
    assert uid in out


# 5) 多 fixture 组合（模拟配置前缀）
def test_generate_fact_no_with_config(default_user_id, predicate_pref_role, mock_prefix_config):
    out = Fact.generate_fact_no(default_user_id, predicate_pref_role)
    assert out.startswith(mock_prefix_config["prefix"])


# 6) 领域模型自动补全：fact_no 缺省时自动生成
def test_fact_model_auto_generate_fact_no(default_user_id):
    fact = Fact(
        user_id=default_user_id,
        predicate=FactPredicateEnum.PREF_ROLE,
        value="后端开发",
        content="目标岗位是后端开发",
    )
    assert fact.fact_no == "u_demo_001:pref_role"

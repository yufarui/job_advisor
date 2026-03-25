"""用户事实的前端展示模型（与 ES 文档字段对齐）。"""

from __future__ import annotations

from entity.domain.fact_domain import Fact


class UserFactView(Fact):
    """列表/详情序列化用；字段同 ``Fact``。"""

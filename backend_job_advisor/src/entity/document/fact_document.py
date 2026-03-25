"""事实文档别名：与 ``Fact`` 同型，兼容旧 import。"""

from __future__ import annotations

from entity.domain.fact_domain import Fact as FactDocument

__all__ = ["FactDocument"]

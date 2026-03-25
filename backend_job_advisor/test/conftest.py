from __future__ import annotations

import sys
from pathlib import Path

import pytest


# 让测试可直接导入 src 下模块（entity/constants/...）
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def default_user_id() -> str:
    return "u_demo_001"


@pytest.fixture
def empty_user_id() -> str:
    return ""


@pytest.fixture
def predicate_pref_role() -> str:
    return "pref_role"


@pytest.fixture
def mock_prefix_config() -> dict[str, str]:
    return {"prefix": ""}

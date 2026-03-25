from __future__ import annotations

import pytest

from agent.review import _process_waiting_fact_confirm
from agent.state import AdvisorTurnState
from constants.fact_predicate_enum import FactPredicateEnum
from constants.sub_task_status_enum import SubTaskStatusEnum
from constants.sub_task_type_enum import SubTaskTypeEnum
from entity.mongo.sub_task import SubTask


class _FakeSubTaskPort:
    def __init__(self) -> None:
        self.updated: list[tuple[str, str, dict]] = []
        self.status_set: list[tuple[str, str, str]] = []

    async def update_sub_task_fields(
        self, task_id: str, sub_task_id: str, *, set_fields: dict
    ) -> bool:
        self.updated.append((task_id, sub_task_id, set_fields))
        return True

    async def set_sub_task_status(self, task_id: str, sub_task_id: str, status) -> bool:
        v = status.value if hasattr(status, "value") else str(status)
        self.status_set.append((task_id, sub_task_id, v))
        return True


class _FakeFactView:
    def __init__(self, *, user_id: str) -> None:
        self.user_id = user_id


class _FakeFactService:
    def __init__(self, *, hit_exists: bool, update_ok: bool = True) -> None:
        self._hit_exists = hit_exists
        self._update_ok = update_ok
        self.update_called = False

    async def get_fact_view(self, user_id: str, fact_no: str):
        if self._hit_exists:
            return _FakeFactView(user_id=user_id)
        return None

    async def update_fact(self, body) -> bool:
        self.update_called = True
        return self._update_ok


def _state() -> AdvisorTurnState:
    return AdvisorTurnState(user_id="u1", user_input="确认")


def _sub(confirm_state: str) -> SubTask:
    return SubTask(
        id="fc1",
        task_id="t1",
        task_type=SubTaskTypeEnum.fact_confirm,
        status=SubTaskStatusEnum.waiting,
        params={
            "confirm_state": confirm_state,
            "predicate": FactPredicateEnum.CONSTRAINT_TIME.value,
            "value": "一周以内",
            "current_fact_content": "可两周后到岗",
            "new_fact_content": "一周以内可到岗",
        },
    )


@pytest.mark.asyncio
async def test_fact_confirm_created_stays_waiting_and_prompts_user():
    port = _FakeSubTaskPort()
    svc = _FakeFactService(hit_exists=True)
    state = _state()

    await _process_waiting_fact_confirm(
        sub=_sub("created"),
        task_id="t1",
        sub_task_port=port,
        fact_service=svc,
        state=state,
    )

    assert any(
        x[2].get("status") == SubTaskStatusEnum.waiting.value and "confirm_message" in x[2].get("params", {})
        for x in port.updated
    )
    assert "检测到事实" in (state.assistant_reply or "")
    assert svc.update_called is False


@pytest.mark.asyncio
async def test_fact_confirm_disagree_cancels_task_without_update():
    port = _FakeSubTaskPort()
    svc = _FakeFactService(hit_exists=True)
    state = _state()

    await _process_waiting_fact_confirm(
        sub=_sub("disagree"),
        task_id="t1",
        sub_task_port=port,
        fact_service=svc,
        state=state,
    )

    assert any(x[2].get("status") == SubTaskStatusEnum.cancelled.value for x in port.updated)
    assert "已取消事实" in (state.assistant_reply or "")
    assert svc.update_called is False


@pytest.mark.asyncio
async def test_fact_confirm_agree_updates_fact_and_marks_success():
    port = _FakeSubTaskPort()
    svc = _FakeFactService(hit_exists=True, update_ok=True)
    state = _state()

    await _process_waiting_fact_confirm(
        sub=_sub("agree"),
        task_id="t1",
        sub_task_port=port,
        fact_service=svc,
        state=state,
    )

    assert ("t1", "fc1", SubTaskStatusEnum.success.value) in port.status_set
    assert svc.update_called is True
    assert "已更新事实" in (state.assistant_reply or "")

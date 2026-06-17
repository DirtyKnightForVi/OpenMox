"""
P1-1: G4 — Budget middleware 纯逻辑测试 (无需后端/LLM)

验证 CommunicationBudgetMiddleware.on_acting 的三条路径:
  1. 无 in_progress 任务 → TeamSay 放行, 不扣 budget
  2. 非 TeamSay 工具 → 直接放行, 不检查 budget
  3. TeamSay(to=momo) → 豁免, 不扣 budget

用法: cd backend && uv run pytest experiment/tests/test_budget_middleware.py -v
"""

import asyncio
import os
import sys
from unittest.mock import MagicMock

_backend_dir = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(_backend_dir, "agentscope", "src"))
sys.path.insert(0, _backend_dir)

import pytest


def _make_tool_call(name: str, input_dict: dict) -> MagicMock:
    tc = MagicMock()
    tc.name = name
    tc.input = input_dict
    return tc


async def _next_handler(**kwargs):
    if False:
        yield


# ═══════════════════════════════════════════════════════════


def test_budget_no_in_progress_task_passes_through():
    """无 in_progress 任务 → TeamSay 放行, 不扣 budget."""
    from src.core.communication_budget_middleware import CommunicationBudgetMiddleware

    dao = MagicMock()
    dao.get_tasks_for_agent.return_value = []

    mw = CommunicationBudgetMiddleware(
        dashboard_dao=dao, agent_id="pm", window_id="w1", momo_id="momo",
    )
    tool_call = _make_tool_call("TeamSay", {"to": "dev", "content": "hi"})

    async def _run():
        async for _ in mw.on_acting(
            agent=MagicMock(),
            input_kwargs={"tool_call": tool_call},
            next_handler=_next_handler,
        ):
            pass

    asyncio.run(_run())
    dao.update_task.assert_not_called()


def test_budget_non_teamsay_tool_passes_through():
    """非 TeamSay 工具 → 放行, 不检查 budget."""
    from src.core.communication_budget_middleware import CommunicationBudgetMiddleware

    dao = MagicMock()
    mw = CommunicationBudgetMiddleware(
        dashboard_dao=dao, agent_id="a", window_id="w", momo_id="momo",
    )
    tool_call = _make_tool_call("Read", {"file_path": "t.txt"})

    async def _run():
        async for _ in mw.on_acting(
            agent=MagicMock(),
            input_kwargs={"tool_call": tool_call},
            next_handler=_next_handler,
        ):
            pass

    asyncio.run(_run())
    dao.get_tasks_for_agent.assert_not_called()
    dao.update_task.assert_not_called()


def test_budget_teamsay_to_leader_is_free():
    """TeamSay(to=momo) → 豁免, 不扣 budget."""
    from src.core.communication_budget_middleware import CommunicationBudgetMiddleware

    dao = MagicMock()
    mw = CommunicationBudgetMiddleware(
        dashboard_dao=dao, agent_id="worker-1", window_id="w", momo_id="momo",
    )
    tool_call = _make_tool_call("TeamSay", {"to": "momo", "content": "report"})

    async def _run():
        async for _ in mw.on_acting(
            agent=MagicMock(),
            input_kwargs={"tool_call": tool_call},
            next_handler=_next_handler,
        ):
            pass

    asyncio.run(_run())
    dao.update_task.assert_not_called()

"""
J 类 — Agent-as-Tool / TeamSay 测试 (5 场景)

⚠️ 部分阻塞: CallAgentTool 硬编码 ConfigDAO(".") (Bug 3)
             Dashboard 工具依赖 Bug 1+2

场景映射:
  J1  momo call_agent(product-manager)
  J2  momo 串行 call 多 Agent
  J3  AgentFromTemplate
  J4  TeamSay(to=momo) → inbox + HintBlock
  J5  TeamSay(to=worker) → WakeupDispatcher

用法: cd backend && uv run pytest experiment/tests/test_agent_tools.py -v
"""

import pytest


@pytest.mark.asyncio
@pytest.mark.skip(reason="CallAgentTool deprecated — migrate to TeamSay inbox/wakeup")
async def test_J1_momo_call_product_manager():
    ...


@pytest.mark.asyncio
@pytest.mark.skip(reason="CallAgentTool deprecated — migrate to TeamSay inbox/wakeup")
async def test_J2_momo_serial_call_multi_agents():
    ...


@pytest.mark.asyncio
@pytest.mark.skip(reason="阻塞于 Bug 1+2 (AgentFromTemplate 依赖 Dashboard)")
async def test_J3_agent_from_template():
    ...


@pytest.mark.asyncio
@pytest.mark.skip(reason="TeamSay 产品集成未完成")
async def test_J4_teamsay_to_momo_inbox_hintblock():
    ...


@pytest.mark.asyncio
@pytest.mark.skip(reason="TeamSay 产品集成未完成")
async def test_J5_teamsay_to_worker_wakeup():
    ...

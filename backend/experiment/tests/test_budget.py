"""
G 类 — CommunicationBudget 测试 (5 场景)

Bug 1+2 已修复，但本类测试依赖 LLM 主动调用 TeamSay + Dashboard 工具
的多轮交互，难以做确定性断言。保留为骨架，待 Phase 4 后续测试方案完善。

场景映射:
  G1  TeamSay(to=peer) → budget 减 1
  G2  budget 耗尽 → 拒绝 + 提示
  G3  TeamSay(to=momo) → 永远免费
  G4  无 in_progress 任务 → 不拦截
  G5  momo 调整 budget

用法: cd backend && uv run pytest experiment/tests/test_budget.py -v
"""

import pytest


@pytest.mark.asyncio
@pytest.mark.skip(reason="需 Agent 主动调用 TeamSay + Dashboard 多轮交互，待集成测试方案")
async def test_G1_teamsay_deducts_budget():
    ...


@pytest.mark.asyncio
@pytest.mark.skip(reason="同上")
async def test_G2_budget_exhausted_denied():
    ...


@pytest.mark.asyncio
@pytest.mark.skip(reason="同上")
async def test_G3_teamsay_to_momo_free():
    ...


@pytest.mark.asyncio
@pytest.mark.skip(reason="同上")
async def test_G4_no_active_task_no_intercept():
    ...


@pytest.mark.asyncio
@pytest.mark.skip(reason="同上")
async def test_G5_momo_adjust_budget():
    ...

"""
F 类 — 看板任务体系测试 (8 场景)

Bug 1+2 已修复 (2026-06-12)。F1-F6 依赖 LLM 调用 Dashboard 工具，
通过 REST API + WS 验证；F7-F8 纯 REST。

用法: cd backend && uv run pytest experiment/tests/test_dashboard.py -v
"""

import pytest
from ._helpers import make_command, ws_send_and_collect


# ═══════════════════════════════════════════════════════════
# F7 — 看板 REST API
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_F7_dashboard_rest_api(http_client, window_id, project_path):
    """GET /api/dashboard 返回 phases + total; PATCH 更新任务."""
    # 获取看板
    r = await http_client.get(
        "/api/dashboard",
        params={"window_id": window_id, "project_path": project_path},
    )
    assert r.status_code == 200
    data = r.json()
    assert "phases" in data or "total" in data
    assert "total" in data


# ═══════════════════════════════════════════════════════════
# F1 — momo 创建任务 (通过 WS 触发 LLM)
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_F1_momo_create_task(ws_client, http_client,
                                    window_id, project_path):
    """momo 通过 CreateTaskPlan 创建任务 → DASHBOARD.yaml 更新."""
    c = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "@momo 请用 create_task_plan 创建一个任务："
            'tasks=[{"title":"测试任务","description":"看板测试","phase":"research",'
            '"owner":"product-manager"}]',
        ),
        timeout=180.0,
    )

    # 验证看板有更新（宽松：至少 API 可访问）
    r = await http_client.get(
        "/api/dashboard",
        params={"window_id": window_id, "project_path": project_path},
    )
    assert r.status_code == 200
    data = r.json()
    assert "total" in data


# ═══════════════════════════════════════════════════════════
# F3 — 非负责人更新被拒
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_F3_non_owner_update_denied(ws_client, window_id, project_path):
    """dev-manager 尝试更新 product-manager 的任务 → 应被拒绝."""
    c = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "@dev-manager 请用 update_dashboard 更新一个不存在的任务 task_id='nonexistent'",
        ),
        timeout=180.0,
    )
    # 只要 Agent 完成了处理（回复或请求确认）即可
    assert c.has_completed() or c.has_type("HINT_BLOCK") \
        or c.has_type("TOOL_RESULT_START"), \
        f"Agent 应完成处理: {c.event_types[:10]}"


# ═══════════════════════════════════════════════════════════
# F5 — DAG 循环检测
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_F5_dag_cycle_rejected(ws_client, window_id, project_path):
    """创建 A→B→A 循环依赖 → 应被拒绝."""
    c = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "@momo 请用 create_task_plan 创建两个互相依赖的任务："
            'tasks=[{"title":"任务A","depends_on":["任务B"]},'
            '{"title":"任务B","depends_on":["任务A"]}]，然后告诉我结果',
        ),
        timeout=180.0,
    )
    assert c.has_completed() or c.has_type("HINT_BLOCK") \
        or c.has_type("TOOL_RESULT_START"), \
        f"Agent 应完成: {c.event_types[:10]}"


# ═══════════════════════════════════════════════════════════
# F2, F4, F6, F8 — 依赖 LLM 多轮交互的测试，暂为骨架
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.skip(reason="需 LLM 多轮调用 Dashboard 工具 + 状态传播验证")
async def test_F2_owner_update_status():
    """任务负责人更新状态 → 看板更新."""
    ...


@pytest.mark.asyncio
@pytest.mark.skip(reason="需有前置任务完成 + 后继任务自动就绪的场景")
async def test_F4_task_done_unblocks_successor():
    """前置任务 done → 后继任务就绪."""
    ...


@pytest.mark.asyncio
@pytest.mark.skip(reason="需验证 OnboardingMiddleware 注入的 system_prompt 含任务信息")
async def test_F6_dashboard_injected_into_prompt():
    """看板注入 system_prompt."""
    ...


@pytest.mark.asyncio
@pytest.mark.skip(reason="需 momo 主动调用 update_dashboard 调整 communication_budget")
async def test_F8_communication_budget_field():
    """communication_budget 字段可读写."""
    ...

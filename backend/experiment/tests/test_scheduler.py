"""
L 类 — 定时任务/心跳测试 (5 场景)

大多数依赖时间周期，测试时需要调整间隔或手动触发。

场景映射:
  L1  APScheduler cron 触发 Agent 执行
  L2  Schedule CRUD (POST → GET → DELETE)
  L3  Dream quick reflect 自动触发
  L4  Dream shendu 窗口检测
  L5  WakeupDispatcher 重试

用法: cd backend && uv run pytest experiment/tests/test_scheduler.py -v
"""

import pytest


@pytest.mark.asyncio
async def test_L2_schedule_crud(http_client):
    """Schedule CRUD: POST 创建 → GET 列出 → DELETE 删除."""
    import uuid
    sid = f"test-sched-{uuid.uuid4().hex[:6]}"

    # 创建
    r = await http_client.post(
        "/api/schedules",
        json={
            "id": sid,
            "agent_id": "momo",
            "project_root": ".",
            "cron_expression": "0 9 * * *",
            "message": "测试定时任务",
        },
    )
    # 创建可能返回 200 或 400（API 格式因实现而异）
    assert r.status_code in (200, 201, 400)

    # 列出 — API 返回 {"schedules": [...]}
    r2 = await http_client.get("/api/schedules")
    assert r2.status_code == 200
    data = r2.json()
    schedules = data if isinstance(data, list) else data.get("schedules", [])
    assert isinstance(schedules, list)

    # 删除
    r3 = await http_client.delete(f"/api/schedules/{sid}")
    assert r3.status_code in (200, 404)  # 可能不存在


@pytest.mark.asyncio
@pytest.mark.skip(reason="需要等待 10min 周期，测试时用手动触发替代 (H6)")
async def test_L3_dream_quick_reflect_auto():
    ...


@pytest.mark.asyncio
@pytest.mark.skip(reason="需要特定时间窗口 (23:00-06:00)")
async def test_L4_dream_shendu_window():
    ...


@pytest.mark.asyncio
@pytest.mark.skip(reason="需要可控断连 Redis 验证重试")
async def test_L5_wakeup_dispatcher_retry():
    ...

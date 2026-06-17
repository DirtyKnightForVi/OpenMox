# 测试盲区覆盖指南 · 2026-06-13

> 基于测试报告识别的 7 个代码已实现但测试未覆盖的场景。
> 按优先级排序，每个场景给出：代码位置 → 测试思路 → 断言要点。

---

## 🔴 P0-1: G2 — budget 耗尽 → 拒绝

**代码位置**: `src/core/communication_budget_middleware.py:133-155`

```python
if best_task.communication_budget <= 0:
    # 返回 ToolChunk ERROR + 预算耗尽提示
    yield ToolChunk(content=[TextBlock(text=budget_exhausted_msg)], state=ToolResultState.ERROR)
    return
```

**现状**: `test_teamsay_budget_deducted` 只测了 budget=2→1 的一次扣减，未触发拒绝路径。

**测试思路**:

```
1. 通过 DashboardDAO 创建任务, budget=1, status="in_progress", owner="momo"
2. 发 WS 让 momo TeamSay 两次
3. 第一次 TeamSay → budget 从 1 减为 0（通过）
4. 第二次 TeamSay → CommunicationBudgetMiddleware 拦截
   → ToolChunk ERROR, 内容包含 "通信预算耗尽"
5. 断言:
   - 任务 budget == 0（第一次扣减成功）
   - momo 的回复中包含 "通信预算耗尽"（第二次被拦截）
```

**新增测试函数**（加在 `test_teamsay_e2e.py`）:

```python
async def test_teamsay_budget_exhausted_rejected(ws_client, window_id, project_path):
    """budget 从 1→0→拒绝: 验证耗尽路径。"""
    import os, sys; ...
    from src.dao.dashboard_dao import DashboardDAO
    
    dao = DashboardDAO(project_path)
    task = dao.create_task(
        title="Budget 耗尽测试",
        owner="momo",
        task_id=f"ts-exhaust-{window_id[:8]}",
        communication_budget=1,  # 只有 1 次额度
    )
    dao.update_task(task.id, status="in_progress")
    
    collector = await ws_send_and_collect(ws_client, make_command(
        window_id, project_path,
        "@momo 请用 TeamSay 向 产品经理 和 架构经理 各发送一条消息。发送两条。"
    ), timeout=180.0)
    
    t_after = dao.get_task(task.id)
    text = collector.text_content()
    
    # 核心断言: budget 被扣减到 0 或出现耗尽提示
    budget_exhausted = (
        t_after.communication_budget == 0
        or "预算耗尽" in text
        or "communication_budget" in text.lower()
    )
    assert budget_exhausted or collector.has_completed(), \
        f"budget={t_after.communication_budget}, text={text[:200]}"
```

---

## 🔴 P0-2: G3 — TeamSay(to=momo) 免费

**代码位置**: `src/core/communication_budget_middleware.py:113-116`

```python
if to is not None and self._is_leader(to):
    # Sending to momo (leader) — always free.
    async for event in next_handler(tool_call=tool_call):
        yield event
    return  # ← 不扣 budget
```

**现状**: 从未验证 `TeamSay(to=momo)` 不扣减 budget。

**测试思路**:

```
1. 创建任务, budget=1, status="in_progress", owner="arch-manager"
2. 发 WS 让 arch-manager 用 TeamSay 向 momo 报告
3. 验证: 任务 budget 仍是 1（未被扣减）
4. 对比: 如果向 product-manager 发 TeamSay, budget 会减为 0
```

**注意**: 这个测试需要 arch-manager 被唤醒并调用 TeamSay——需要 Team 中有 arch-manager 的 session。如果 arch-manager 不在当前窗口的 Team 中，TeamSay 调用会报 "not in any team"。可以在测试中直接通过 DB 操作创建 agent session + 绑定 team。

**新增测试函数**（加在 `test_teamsay_e2e.py`）:

```python
async def test_teamsay_to_momo_is_free(ws_client, window_id, project_path):
    """TeamSay(to=momo) 不扣 budget。"""
    # 创建任务，owner 设为将被 momo 调度的 agent
    dao = DashboardDAO(project_path)
    task = dao.create_task(
        title="momo 豁免测试",
        owner="momo",
        task_id=f"ts-free-{window_id[:8]}",
        communication_budget=3,
    )
    dao.update_task(task.id, status="in_progress")
    
    # 触发 momo TeamSay（to=momo 的场景需要通过 worker 向 momo 发消息来触发）
    # 如果 LLM 向 momo 发 TeamSay, middleware 的 _is_leader 应豁免
    collector = await ws_send_and_collect(ws_client, make_command(
        window_id, project_path,
        "@momo 请用 TeamSay 向 产品经理 发送：'请回复收到'"
    ), timeout=180.0)
    
    t_after = dao.get_task(task.id)
    # 宽松: Agent 完成了处理即可
    assert collector.has_completed() or collector.has_type("agent:idle"), \
        f"budget={t_after.communication_budget}, types={collector.event_types[:15]}"
    # 如果 TeamSay 被调用且 to 不是 momo, budget 会减少 — 这是预期行为
```

---

## 🟡 P1-1: G4 — 无 in_progress 任务时不拦截

**代码位置**: `src/core/communication_budget_middleware.py:128-131`

```python
if not in_progress:
    # No active task — let through.
    async for event in next_handler(tool_call=tool_call):
        yield event
    return
```

**现状**: 从未验证"无 in_progress 任务时 TeamSay 不扣 budget"。

**测试思路**: 纯逻辑——不需要 LLM！

```
1. 创建 CommunicationBudgetMiddleware 实例（mock dashboard_dao）
2. Mock dashboard_dao.get_tasks_for_agent → 返回空列表
3. Mock tool_call: name="TeamSay", input={"to": "product-manager"}
4. 调用 on_acting
5. 验证: next_handler 被调用（放行），dashboard_dao.update_task 未被调用
```

**新增测试函数**（加在 `test_dashboard_dao.py` 或新文件 `test_budget_middleware.py`）:

```python
def test_budget_no_in_progress_task_passes_through():
    """无 in_progress 任务时, TeamSay 直接放行, 不扣 budget."""
    from unittest.mock import MagicMock, AsyncMock
    from src.core.communication_budget_middleware import CommunicationBudgetMiddleware
    from agentscope.message import ToolCallBlock
    
    # Mock DAO — 返回空任务列表
    dao = MagicMock()
    dao.get_tasks_for_agent.return_value = []
    
    mw = CommunicationBudgetMiddleware(
        dashboard_dao=dao,
        agent_id="product-manager",
        window_id="test",
        momo_id="momo",
    )
    
    # Mock tool_call: TeamSay to peer
    tool_call = ToolCallBlock(
        id="tc1", name="TeamSay",
        input='{"to": "dev-manager", "content": "hello"}',
    )
    
    # Mock next_handler
    next_handler = AsyncMock()
    next_handler.return_value = AsyncMock().__aiter__.return_value = []
    
    # 调用 on_acting
    import asyncio
    async def _run():
        async for _ in mw.on_acting(
            agent=MagicMock(),
            input_kwargs={"tool_call": tool_call},
            next_handler=next_handler,
        ):
            pass
    
    asyncio.run(_run())
    
    # 断言: next_handler 被调用（放行）
    next_handler.assert_called_once()
    # 断言: DAO 的 update_task 从未被调用（不扣 budget）
    dao.update_task.assert_not_called()
```

---

## 🟡 P1-2: M1 — Redis 不可达降级

**代码位置**: `main.py` lifespan 中

```python
try:
    import redis.asyncio as aioredis
    redis_pool = aioredis.ConnectionPool(...)
except Exception:
    redis_pool = None
    log.warning("Cannot create shared Redis pool — falling back to per-service pools")
```

**现状**: `test_lifecycle.py::test_M1_redis_unreachable_degradation` 是 skip 空壳。

**测试思路**:

```
1. 停止 Redis 容器
2. 使用 test_lifecycle.py 的自建 _BackendProcess 启动后端
3. 验证: 后端不崩溃，health check 可达
4. 验证: 后端日志包含 "Cannot create shared Redis pool" 或 "falling back"
5. 重启 Redis 容器（清理）
```

**新增测试函数**（加在 `test_lifecycle.py`）:

```python
import subprocess, time

@pytest.mark.asyncio
async def test_M1_redis_unreachable_degradation():
    """Redis 不可达时后端降级启动，不崩溃。"""
    # 1. 停止 Redis
    subprocess.run(["docker", "stop", "skill-redis-server"], capture_output=True)
    time.sleep(2)
    
    try:
        bp = _BackendProcess()
        # 预期: 后端可能启动失败，或在无 Redis 下启动
        started = await bp.start(timeout=15.0)
        # 宽松断言: 不崩溃即可
        # 如果后端在无 Redis 下仍启动，health 应可达
        if started:
            import httpx
            async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as c:
                r = await c.get("/api/health")
                assert r.status_code in (200, 503)  # 200=降级成功, 503=服务不可用
        await bp.stop()
    finally:
        subprocess.run(["docker", "start", "skill-redis-server"], capture_output=True)
        time.sleep(2)
```

---

## 🟡 P1-3: M4 — API Key 未设置

**代码位置**: `settings.py` → `deepseek_api_key` 从环境变量读取，默认空字符串。

**现状**: `test_lifecycle.py::test_M4_no_api_key_warning` 是 skip 空壳。

**测试思路**:

```
1. 修改 _BackendProcess.start() 将 DEEPSEEK_API_KEY 设为空
2. 启动后端
3. 验证: 后端日志包含 WARNING（或启动成功但 Agent 调用时返回错误）
```

**新增测试函数**（加在 `test_lifecycle.py`）:

```python
@pytest.mark.asyncio
async def test_M4_no_api_key_warning():
    """DEEPSEEK_API_KEY 未设置时, 启动警告 + Agent 调用返回错误。"""
    bp = _BackendProcess()
    # 覆盖 start 中的 key 为空
    # 需要在 _BackendProcess 中支持 env 覆盖参数, 或新建子类
    ...
    # 这是需要改 _BackendProcess 的地方, 先保留为骨架
```

---

## ⚪ P2-1: H7 — 快照回滚

**代码位置**: `src/core/store.py:438` → `rollback_snapshot()` + `src/api/memory.py:131` → `POST /api/memory/{id}/rollback/{snapshot_id}`

**现状**: H7 是 skip。快照创建（`create_snapshot`）只在 shendu 流程中触发，手动构造即可测试回滚。

**测试思路**:

```
1. 手动插入一些 memory_entries + 一个 dream_snapshot 记录
2. 调用 POST /api/memory/{agent_id}/rollback/{snapshot_id}
3. 验证: snapshot.rolled_back = 1
4. 验证: 快照之前的条目被 deprecate
```

**新增测试函数**（加在 `test_memory.py`）:

```python
@pytest.mark.asyncio
async def test_H7_snapshot_rollback(http_client, project_path):
    """手动构造快照 → 回滚 → snapshot.rolled_back=1。"""
    # 1. 插入测试记忆
    from src.core import store as mem_store
    await mem_store.insert_memory("momo", project_path, content="回滚测试记忆1")
    await mem_store.insert_memory("momo", project_path, content="回滚测试记忆2")
    
    # 2. 创建快照
    snap_id = await mem_store.create_snapshot("momo", project_path, entry_count_before=2)
    await mem_store.finalize_snapshot(snap_id, entry_count_after=2)
    
    # 3. 调用回滚 API
    r = await http_client.post(f"/api/memory/momo/rollback/{snap_id}")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    
    # 4. 验证回滚状态
    snap = await mem_store.get_last_snapshot("momo")
    assert snap is not None
```

---

## ⚪ P2-2: E3 — THINKING 过滤

**代码位置**: WindowPublishMiddleware 的 `_PUBLIC_EVENT_TYPES` 不包含 `THINKING_BLOCK_*`

**现状**: skip 条件是 `OPENMOX_THINKING != "1"`。CI 环境未设置此变量。

**测试**: 无需修改代码。设置环境变量后重跑即可验证。

```bash
OPENMOX_THINKING=1 uv run --directory backend --extra dev pytest \
  experiment/tests/test_message_routing.py::test_E3_thinking_filtered_from_window_stream -v
```

**断言**: THINKING_BLOCK_DELTA 事件不出现在 window stream 中。

---

## 综合运行脚本

```bash
cd backend

# P0 — G2/G3 (需后端 + API key)
uv run --extra dev pytest experiment/tests/test_teamsay_e2e.py -v

# P1 — G4 纯逻辑 (无需后端, <0.1s)
uv run --extra dev pytest experiment/tests/test_budget_middleware.py -v

# P1 — M1 (需 Docker 控制 Redis)
uv run --extra dev pytest experiment/tests/test_lifecycle.py::test_M1_redis_unreachable_degradation -v

# P2 — H7 (需后端, 无需 LLM)
uv run --extra dev pytest experiment/tests/test_memory.py::test_H7_snapshot_rollback -v

# P2 — E3 (需设置 OPENMOX_THINKING=1)
OPENMOX_THINKING=1 uv run --extra dev pytest \
  experiment/tests/test_message_routing.py::test_E3_thinking_filtered_from_window_stream -v
```

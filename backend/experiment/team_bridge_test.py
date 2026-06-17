"""
Team Bridge 验证实验 — 不修改生产代码，验证路线 3B 的 5 个未知点。

验证项:
  1. set_session_team_id 能否用于 OpenMox session？
  2. TeamSay directory 构建能否通过 OpenMoxRedisStorage.get_agent() 正确解析名称？
  3. InboxMiddleware + WakeupDispatcher 完整链路？
  4. 被调 Agent 回复能否出现在 window stream？
  5. TeamSay 要求调用方 session 在 Team 上下文中？

用法: cd backend && uv run python experiment/team_bridge_test.py

前提: 后端运行在 localhost:8000
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

# ── 路径注入 ──────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR / "agentscope" / "src"))
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-xxxxxxxxxx")
os.environ.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
os.environ.setdefault("DEEPSEEK_MODEL", "deepseek-v4-flash")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6480")
os.environ.setdefault("OPENMOX_THINKING", "0")

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
TEST_PROJECT = BACKEND_DIR.parent / "TestProject"


def _log(section: str, msg: str) -> None:
    print(f"  [{section}] {msg}")


# ═══════════════════════════════════════════════════════════
# Phase 1: Storage 层验证（不依赖后端进程）
# ═══════════════════════════════════════════════════════════


async def phase1_storage() -> dict:
    """验证: 通过 storage API 创建 Team + 关联现有 Agent。"""
    import redis.asyncio as aioredis

    _log("P1", "连接 Redis ...")
    r = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0,
                       socket_connect_timeout=5, decode_responses=True)
    await r.ping()
    _log("P1", "Redis OK")

    # 清空测试数据
    await r.flushdb()
    _log("P1", "Redis flushed")

    from src.core.openmox_redis_storage import OpenMoxRedisStorage
    from agentscope.app.storage import TeamRecord, TeamData, SessionConfig, SessionSource
    from src.dao.config_dao import ConfigDAO

    # 初始化 storage（需要 Redis 连接参数）
    conn_pool = aioredis.ConnectionPool(
        host=REDIS_HOST, port=REDIS_PORT, db=0,
        decode_responses=True, socket_connect_timeout=10,
    )
    storage = OpenMoxRedisStorage(
        project_root=str(TEST_PROJECT.resolve()),
        connection_pool=conn_pool,
    )
    await storage.__aenter__()
    _log("P1", "Storage ready")

    # ── 1. 读取项目中的 Agent ──
    dao = ConfigDAO(TEST_PROJECT)
    agents = dao.list_agents()
    _log("P1", f"项目中有 {len(agents)} 个 Agent:")
    for a in agents:
        _log("P1", f"  - {a.id} ({a.name}) is_momo={a.is_momo}")

    # ── 2. 注册 Agent 到 Redis ──
    for a in agents:
        ok = await storage.ensure_agent_from_path("openmox", a.id, str(TEST_PROJECT))
        _log("P1", f"  register {a.id}: {'OK' if ok else 'FAIL'}")

    # ── 3. 创建 sessions ──
    from src.core.settings import get_settings
    from agentscope.app.storage import ChatModelConfig

    s = get_settings()
    model_cfg = ChatModelConfig(
        type="deepseek_chat",
        credential_id="default",
        model=s.deepseek_model,
        parameters={},
    )
    window_id = f"team_test_{uuid.uuid4().hex[:8]}"

    for a in agents:
        session_id = f"{window_id}:{a.id}"
        await storage.upsert_session(
            "openmox", a.id,
            config=SessionConfig(workspace_id="default", chat_model_config=model_cfg),
            session_id=session_id,
            source=SessionSource.USER,
        )
        _log("P1", f"  session: {session_id[:40]}")

    # ── 4. 创建 Team ──
    momo_id = dao.get_momo_id()
    momo_session = f"{window_id}:{momo_id}"

    team = TeamRecord(
        user_id="openmox",
        session_id=momo_session,
        data=TeamData(
            name="OpenMox 验证项目组",
            description="验证 TeamSay 链路的测试项目",
            member_ids=[],
        ),
    )
    await storage.upsert_team("openmox", team)
    team_id = team.id
    _log("P1", f"Team created: {team_id} ({team.data.name})")

    # ── 5. 绑定 session → Team ──
    for a in agents:
        session_id = f"{window_id}:{a.id}"
        await storage.set_session_team_id("openmox", session_id, team_id)
        team.data.member_ids.append(a.id)
        _log("P1", f"  bind {a.id} → team {team_id[:12]}")

    # 更新 team 的 member_ids
    await storage.upsert_team("openmox", team)
    _log("P1", f"Team member_ids: {team.data.member_ids}")

    # ── 6. 验证关联 ──
    for a in agents:
        session_id = f"{window_id}:{a.id}"
        sess = await storage.get_session("openmox", a.id, session_id)
        if sess:
            _log("P1", f"  verify {a.id}: team_id={sess.team_id}")
        else:
            _log("P1", f"  verify {a.id}: SESSION NOT FOUND!")

    await storage.__aexit__(None, None, None)
    await r.aclose()

    return {
        "ok": True,
        "team_id": team_id,
        "window_id": window_id,
        "agents": [(a.id, a.name) for a in agents],
        "momo_id": momo_id,
        "momo_session": momo_session,
    }


# ═══════════════════════════════════════════════════════════
# Phase 2: TeamSay 路由验证（依赖后端运行）
# ═══════════════════════════════════════════════════════════


async def phase2_teamsay_routing(ctx: dict) -> None:
    """验证: 通过 TeamSay 向已注册的 Agent 发送消息，检查 inbox + wakeup。"""
    import redis.asyncio as aioredis

    _log("P2", "连接 Redis ...")
    r = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0,
                       socket_connect_timeout=5, decode_responses=True)

    from src.core.openmox_redis_storage import OpenMoxRedisStorage
    from agentscope.app.message_bus import RedisMessageBus

    conn_pool = aioredis.ConnectionPool(
        host=REDIS_HOST, port=REDIS_PORT, db=0,
        decode_responses=True, socket_connect_timeout=10,
    )
    storage = OpenMoxRedisStorage(
        project_root=str(TEST_PROJECT.resolve()),
        connection_pool=conn_pool,
    )
    await storage.__aenter__()

    message_bus = RedisMessageBus(connection_pool=conn_pool)
    await message_bus.__aenter__()

    team_id = ctx["team_id"]
    window_id = ctx["window_id"]
    momo_session = ctx["momo_session"]
    momo_id = ctx["momo_id"]

    # ── 1. 验证 momo session 的 team_id ──
    sess = await storage.get_session("openmox", momo_id, momo_session)
    _log("P2", f"momo session: team_id={sess.team_id if sess else 'NOT FOUND'}")

    if sess is None or sess.team_id is None:
        _log("P2", "❌ momo session 不在 Team 中！TeamSay 将失败。")
        return

    # ── 2. 查找一个非 momo 的 Agent ──
    target = None
    for aid, aname in ctx["agents"]:
        if aid != momo_id:
            target = (aid, aname)
            break

    if target is None:
        _log("P2", "❌ 没有非 momo Agent 可测试")
        return

    target_id, target_name = target
    target_session = f"{window_id}:{target_id}"
    _log("P2", f"目标: {target_name} ({target_id}), session={target_session[:40]}")

    # ── 3. 构造 TeamSay HintBlock ──
    from agentscope.message import HintBlock

    hint = HintBlock(
        hint=f'<team-message from="momo">\n你好 {target_name}，请简要回复收到。\n</team-message>',
        source="momo",
    )
    payload = hint.model_dump(mode="json")

    # ── 4. inbox_push + enqueue_wakeup ──
    await message_bus.inbox_push(target_session, payload)
    _log("P2", f"inbox_push → {target_session[:40]}")

    await message_bus.enqueue_wakeup(
        user_id="openmox",
        session_id=target_session,
        agent_id=target_id,
    )
    _log("P2", f"enqueue_wakeup → {target_session[:40]}")

    # ── 5. 验证 inbox 中有消息 ──
    await asyncio.sleep(0.5)
    entries = await message_bus.inbox_drain(target_session, max_count=10)
    _log("P2", f"inbox_drain: {len(entries)} entries (0=已被 InboxMiddleware 消费)")

    # ── 6. 验证 wakeup 队列 ──
    wakeups = await message_bus.dequeue_wakeups(max_count=10)
    _log("P2", f"dequeue_wakeups: {len(wakeups)} entries (0=已被 WakeupDispatcher 消费)")

    await message_bus.__aexit__(None, None, None)
    await storage.__aexit__(None, None, None)
    await r.aclose()


# ═══════════════════════════════════════════════════════════
# Phase 3: 完整 WebSocket 链路验证（依赖后端运行）
# ═══════════════════════════════════════════════════════════


async def phase3_ws_full_chain(ctx: dict) -> None:
    """验证: 通过 WS 发送消息触发 momo → TeamSay → worker → window stream。

    前提: 后端在 localhost:8000 运行。
    使用 Phase 1 创建的 Team 和 session。
    """
    import websockets
    from agentscope.message import Msg

    _log("P3", "连接 WebSocket ...")

    window_id = ctx["window_id"]
    momo_id = ctx["momo_id"]
    project_path = str(TEST_PROJECT.resolve())

    # Find a non-momo target
    target = None
    for aid, aname in ctx["agents"]:
        if aid != momo_id:
            target = (aid, aname)
            break
    if target is None:
        _log("P3", "❌ 无目标 Agent")
        return
    target_id, target_name = target

    try:
        ws = await asyncio.wait_for(
            websockets.connect("ws://localhost:8000/ws", ping_interval=30),
            timeout=10.0,
        )
    except Exception as e:
        _log("P3", f"❌ WS 连接失败: {e}")
        return

    # 消费握手消息
    for _ in range(2):
        try:
            await asyncio.wait_for(ws.recv(), timeout=3.0)
        except asyncio.TimeoutError:
            break

    # ── 发送命令：让 momo 通过 TeamSay 呼叫同事 ──
    cmd = {
        "type": "pilotdeck-command",
        "command": f"请用 TeamSay 工具向 {target_name} 发送消息：'你好，请回复收到'。然后告诉我结果。",
        "options": {
            "sessionKey": window_id,
            "sessionId": window_id,
            "projectPath": project_path,
            "cwd": project_path,
        },
    }
    await ws.send(json.dumps(cmd, ensure_ascii=False))
    _log("P3", f"发送: {cmd['command'][:60]}")

    # ── 收集事件 ──
    events = []
    deadline = time.time() + 180.0
    silent = 0
    while time.time() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
            silent = 0
        except asyncio.TimeoutError:
            silent += 1
            if events and silent < 6:
                continue
            break
        try:
            evt = json.loads(raw)
        except json.JSONDecodeError:
            continue
        events.append(evt)
        t = evt.get("type", "?")
        agent = evt.get("_agent_id", "")
        detail = ""
        if t == "TOOL_CALL_END":
            detail = f" tool={evt.get('tool_name', evt.get('name', '?'))}"
        elif t in ("REPLY_END", "REQUIRE_USER_CONFIRM"):
            detail = " ← 完成"
        _log("P3", f"  事件: {t} agent={agent[:20]}{detail}")
        if t in ("REPLY_END", "REQUIRE_USER_CONFIRM"):
            break

    await ws.close()

    # ── 分析结果 ──
    types = [e.get("type") for e in events]
    _log("P3", f"收到 {len(events)} 个事件: {types}")

    # 检查 TeamSay 是否被调用
    team_say_calls = [
        e for e in events
        if e.get("type") == "TOOL_CALL_END" and "TeamSay" in str(e.get("tool_name", ""))
    ]
    if team_say_calls:
        _log("P3", f"✅ momo 调用了 TeamSay ({len(team_say_calls)} 次)")
    else:
        _log("P3", "⚠️ momo 未调用 TeamSay（LLM 可能选择了其他方式）")

    # 检查是否有来自 target agent 的事件
    target_events = [
        e for e in events
        if e.get("_agent_id") == target_id
    ]
    if target_events:
        _log("P3", f"✅ 收到来自 {target_name} 的 {len(target_events)} 个事件")
    else:
        _log("P3", f"⚠️ 未收到来自 {target_name} 的事件（wakeup 可能未触发或 _agent_id 未注入）")

    # 检查完整事件链
    has_human = "human_message" in types
    has_reply_start = "REPLY_START" in types
    has_reply_end = "REPLY_END" in types
    has_confirm = "REQUIRE_USER_CONFIRM" in types
    _log("P3", f"事件链: human={has_human} start={has_reply_start} "
                f"end={has_reply_end} confirm={has_confirm}")


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════


async def main():
    print("=" * 60)
    print("Team Bridge 验证实验 — 路线 3B 可行性评估")
    print("=" * 60)

    # Phase 1
    print("\n── Phase 1: Storage 层验证 ──")
    ctx = await phase1_storage()
    if not ctx["ok"]:
        print("❌ Phase 1 失败，中止")
        return

    print("\n── Phase 2: TeamSay 路由验证 ──")
    await phase2_teamsay_routing(ctx)

    print("\n── Phase 3: WebSocket 全链路 ──")
    await phase3_ws_full_chain(ctx)

    print("\n" + "=" * 60)
    print("实验完成。检查上方日志确认 5 个未知点的状态。")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

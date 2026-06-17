"""End-to-end integration test — simulated multi-agent collaboration.

S1: mvp — momo creates tasks, PD/Dev/Arch execute via chain trigger

This is NOT a mock test. It uses the real AgentScope agent with DeepSeek API.
Run only when DEEPSEEK_API_KEY is set.

Usage:
  cd backend && DEEPSEEK_API_KEY=sk-xxx python experiment/e2e_collab_test.py

What to watch in the logs:
  [fanout]    Agent X: seeded N blocks...       ← context seeding working
  [fanout]    Agent X: state persisted...        ← Redis state saved
  [memory]    agent=X captured N entries         ← MemoryCaptureMiddleware fired
  [chat]      Chain trigger depth=N              ← Agent→Agent @ chain working
  [chat]      No @mention → defaulting to momo   ← default routing working

Preconditions:
  - Project must exist with .Agents/ and .Project/
  - At minimum momo must be configured (pm-secretary)
  - Agent_Sets/ must have templates
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR / "agentscope" / "src"))
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))


# ── Config ────────────────────────────────────────────

PROJECT_ROOT = Path(os.environ.get("E2E_PROJECT", str(BACKEND_DIR / "e2e_test_project")))
assert PROJECT_ROOT.exists(), f"Project not found: {PROJECT_ROOT}. Run: mkdir -p {PROJECT_ROOT}/.Agents {PROJECT_ROOT}/.Project"


async def setup_project():
    """Ensure project has at minimum momo configured."""
    from src.dao import ConfigDAO
    from src.dao.config_dao import ConfigDAO as DAO

    dao = DAO(PROJECT_ROOT)
    dao.init_project(str(PROJECT_ROOT))

    agents = dao.list_agents()
    if not agents:
        print("Creating momo from template...")
        cfg = dao.create_agent(
            agent_id="pm-secretary",
            template_id="pm-secretary",
            name="秘书",
        )
        print(f"  → momo created: {cfg.id} ({cfg.name})")

    # Optionally create more agents
    for tmpl_id in ["product-manager", "dev-manager", "arch-manager"]:
        if not dao.get_agent(tmpl_id):
            cfg = dao.create_agent(
                agent_id=tmpl_id,
                template_id=tmpl_id,
                name={"product-manager": "产品经理", "dev-manager": "开发经理", "arch-manager": "架构经理"}.get(tmpl_id, tmpl_id),
            )
            print(f"  → {cfg.id} created")

    print(f"\nProject ready: {PROJECT_ROOT}")
    print(f"Agents: {[a.id for a in dao.list_agents()]}")


# ═══════════════════════════════════════════════════════
# Scenario S1: Momo creates task plan → PD/Dev execute
# ═══════════════════════════════════════════════════════

async def scenario_s1_momo_creates_task_plan():
    """
    Human: "@momo 做一个简单的任务分解：我需要了解竞品，然后开发一个demo，最后评审"
    Expected flow:
      1. MentionRouter → ["momo"]
      2. FanoutStreamer starts momo
      3. Context seeding: momo has no Redis state → "no Redis state yet"
      4. momo's system_prompt includes dashboard (empty for now)
      5. momo calls CreateTaskPlan to create 3 DAG tasks
      6. momo replies with task summary → chat.py chain-triggers @PD if present
      7. momo's state persisted to Redis
    """
    from src.orchestration.router import MentionRouter
    from src.orchestration.fanout import FanoutStreamer
    from src.core.logging import LogContext

    tid = LogContext.set_trace_id()
    print(f"\n{'='*60}")
    print(f"SCENARIO S1: trace={tid[:12]}")
    print(f"{'='*60}")

    router = MentionRouter()
    message = "@momo 做一个简单的任务分解：我需要了解竞品，然后开发一个demo，最后评审"
    mentioned, clean = router.parse(message)
    print(f"  MentionRouter → @{mentioned} | clean='{clean[:40]}...'")
    assert mentioned == ["momo"], f"Expected [momo], got {mentioned}"

    window_id = f"e2e_window_{int(time.time())}"

    events = []

    async def on_event(evt):
        """Mock front-end: collect events + print summary."""
        events.append(evt)
        etype = evt.get("type", "?")
        agent = evt.get("_agent_id", "?")
        if etype in ("TEXT_BLOCK_DELTA",):
            delta = evt.get("delta", "")
            if delta:
                print(f"  🌊 [{agent}] {delta}", end="", flush=True)
        elif etype in ("REPLY_START", "REPLY_END", "TOOL_CALL_END", "TOOL_RESULT_END"):
            print(f"\n  📍 [{agent}] {etype}")

    streamer = FanoutStreamer(str(PROJECT_ROOT), window_id=window_id)
    results = await streamer.stream(
        agent_ids=["momo"],
        message=clean,
        on_event=on_event,
    )

    print(f"\n  ✅ momo reply: {len(events)} events, {len(results)} results")
    for r in results:
        print(f"     [{r['agent_id']}] {r['text'][:100]}..." if r["text"] else f"     [{r['agent_id']}] (no text)")

    # ── Verify ────────────────────────────────────────
    from src.dao import ConfigDAO
    dao = ConfigDAO(str(PROJECT_ROOT))
    from src.dao.dashboard_dao import DashboardDAO
    dash = DashboardDAO(str(PROJECT_ROOT))
    tasks = dash.get_all_tasks()

    print(f"\n  📊 Dashboard: {len(tasks)} tasks")
    for t in tasks:
        print(f"     {t.id} | {t.title:20s} | @{t.owner:15s} | {t.status:10s} | depends_on={t.depends_on}")

    # Check Redis state
    from src.core.session_store import get_session_state
    state = await get_session_state(window_id)
    ctx_len = len(state.get("context", [])) if state else 0
    print(f"  🗄️  Redis state: {ctx_len} msgs in context")

    # Check memory
    from src.core import store as mem_store
    mems = await mem_store.list_memory(agent_id="momo", limit=10)
    print(f"  🧠 Memory: {len(mems)} entries for momo")
    for m in mems:
        print(f"     [{m['type']}] {m['content'][:80]}...")

    return results, tasks, state


# ═══════════════════════════════════════════════════════
# Scenario S3: No @mention → default to momo
# ═══════════════════════════════════════════════════════

async def scenario_s3_default_momo():
    """
    Human: "项目进度怎么样了" (no @mention)
    Expected:
      - MentionRouter → []
      - Default to momo
      - momo reads DASHBOARD from system_prompt
    """
    from src.orchestration.router import MentionRouter
    from src.orchestration.fanout import FanoutStreamer
    from src.core.logging import LogContext

    tid = LogContext.set_trace_id()
    print(f"\n{'='*60}")
    print(f"SCENARIO S3: trace={tid[:12]}")
    print(f"{'='*60}")

    router = MentionRouter()
    message = "项目进度怎么样了"
    mentioned, clean = router.parse(message)
    print(f"  MentionRouter → @{mentioned} | clean='{clean}'")
    assert mentioned == [], f"Expected [], got {mentioned}"

    window_id = f"e2e_window_{int(time.time())}"

    events = []

    async def on_event(evt):
        events.append(evt)
        etype = evt.get("type", "?")
        agent = evt.get("_agent_id", "?")
        if etype in ("TEXT_BLOCK_DELTA",):
            delta = evt.get("delta", "")
            if delta:
                print(f"  🌊 [{agent}] {delta}", end="", flush=True)

    streamer = FanoutStreamer(str(PROJECT_ROOT), window_id=window_id)
    results = await streamer.stream(
        agent_ids=[],  # empty → will be filled by chat.py in real flow
        message=clean,
        on_event=on_event,
    )

    print(f"\n  ✅ default routing handled by caller ({len(events)} events)")
    return results


# ═══════════════════════════════════════════════════════
# Scenario S2: PD complete task → chain trigger Dev
# ═══════════════════════════════════════════════════════

async def scenario_s2_pd_completes_task():
    """
    Human: "@product-manager 完成你的竞品分析任务，标记为完成"
    Expected:
      - PD wakes up with context seeded from Redis
      - PD calls UpdateDashboard(task_id, status=done)
      - tool returns "以下任务已就绪：@dev-manager → demo 开发"
      - PD might mention @dev-manager → chain trigger
    """
    from src.orchestration.router import MentionRouter
    from src.orchestration.fanout import FanoutStreamer
    from src.core.logging import LogContext

    tid = LogContext.set_trace_id()
    print(f"\n{'='*60}")
    print(f"SCENARIO S2: trace={tid[:12]}")
    print(f"{'='*60}")

    router = MentionRouter()
    message = "@product-manager 完成你的竞品分析任务，标记为完成"
    mentioned, clean = router.parse(message)
    print(f"  MentionRouter → @{mentioned} | clean='{clean[:40]}...'")

    window_id = f"e2e_window_{int(time.time())}"

    events = []

    async def on_event(evt):
        events.append(evt)
        etype = evt.get("type", "?")
        agent = evt.get("_agent_id", "?")
        if etype in ("TEXT_BLOCK_DELTA",):
            delta = evt.get("delta", "")
            if delta:
                print(f"  🌊 [{agent}] {delta}", end="", flush=True)
        elif etype in ("TOOL_CALL_END", "TOOL_RESULT_END"):
            print(f"\n  🔧 [{agent}] {etype}: {evt.get('name','?')}")

    streamer = FanoutStreamer(str(PROJECT_ROOT), window_id=window_id)
    results = await streamer.stream(
        agent_ids=mentioned,
        message=clean,
        on_event=on_event,
    )

    print(f"\n  ✅ PD reply: {len(events)} events")
    for r in results:
        print(f"     [{r['agent_id']}] {r['text'][:120]}..." if r["text"] else f"     [{r['agent_id']}] (no text)")

    # Verify task status
    from src.dao.dashboard_dao import DashboardDAO
    dash = DashboardDAO(str(PROJECT_ROOT))
    tasks = dash.get_all_tasks()
    for t in tasks:
        print(f"  📊 {t.id} | {t.title:20s} | {t.status}")

    return results


# ═══════════════════════════════════════════════════════

async def main():
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("⚠️  DEEPSEEK_API_KEY not set. Skipping LLM-dependent tests.")
        print("   Set it to run real agent scenarios.")
        return

    await setup_project()

    # Run scenarios sequentially
    await scenario_s1_momo_creates_task_plan()
    await scenario_s3_default_momo()
    await scenario_s2_pd_completes_task()

    print(f"\n{'='*60}")
    print("All scenarios completed ✅")
    print(f"Check the logs above for:")
    print("  [fanout] Agent X: seeded N blocks     ← context from Redis")
    print("  [fanout] Agent X: state persisted     ← Redis save")
    print("  [memory] agent=X captured N entries   ← MemoryCapture")
    print("  [chat]   Chain trigger depth=N        ← chain working")
    print("  [chat]   No @mention → defaulting     ← default routing")


if __name__ == "__main__":
    asyncio.run(main())

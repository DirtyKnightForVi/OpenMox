"""Experiment: WriteSharedMemoryTool + dual-layer memory injection.

Validates:
  1. WriteSharedMemory writes scope="shared" entries
  2. Non-momo is denied
  3. _format_private_memories renders private section
  4. _format_shared_memories renders shared section
  5. OnboardingMiddleware injects both sections separately
  6. build_dashboard_tools includes WriteSharedMemory for momo

Run: cd backend && .venv/bin/python experiment/memory_shared_test.py
"""

import os, sys, asyncio, tempfile, shutil
from pathlib import Path

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BACKEND_DIR, "agentscope", "src"))
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)


def setup():
    root = Path(tempfile.mkdtemp(prefix="mox_sm_"))
    (root / ".Project").mkdir(parents=True, exist_ok=True)
    (root / ".Agents").mkdir(parents=True, exist_ok=True)
    return root


def teardown(root):
    if root.exists():
        shutil.rmtree(str(root), ignore_errors=True)


async def main():
    results = []
    def ck(name, ok): results.append((name, "✅" if ok else "❌"))

    # ── 1. Non-momo denied ──────────────
    try:
        from src.dao.dashboard_dao import DashboardDAO
        from src.core.dashboard_tools import WriteSharedMemoryTool

        root = setup()
        dao = DashboardDAO(root)
        tool = WriteSharedMemoryTool(
            dao=dao, dashboard_dao=dao,
            agent_id="dev-manager", is_momo=False, window_id="w1",
        )
        perm = await tool.check_permissions({}, None)
        assert perm.behavior.value == "deny"
        assert "momo" in str(perm.message).lower()
        print(f"  ✅ non-momo denied: {perm.message}")
        ck("non_momo", True)
    except Exception as e:
        print(f"  ❌ non_momo: {e}")
        ck("non_momo", False)
    finally:
        teardown(root)

    # ── 2. Momo writes shared memory ───
    try:
        import src.core.store as store_mod
        store_mod._db = None
        await store_mod.get_db(":memory:")

        from src.dao.dashboard_dao import DashboardDAO
        from src.core.dashboard_tools import WriteSharedMemoryTool

        root = setup()
        dao = DashboardDAO(root)
        tool = WriteSharedMemoryTool(
            dao=dao, dashboard_dao=dao,
            agent_id="momo", is_momo=True, window_id="w1",
        )
        result = await tool.__call__(
            content="项目决定：采用微服务架构 + PG 主库",
            type="decision",
            importance=0.9,
        )
        assert "共同记忆已写入" in result

        # Verify in DB
        entries = await store_mod.list_memory("momo", scope="shared")
        assert len(entries) == 1
        assert entries[0]["scope"] == "shared"
        assert entries[0]["type"] == "decision"
        assert "微服务架构" in entries[0]["content"]
        assert entries[0]["importance"] == 0.9
        print(f"  ✅ shared memory written: {result}")
        await store_mod.close_db()
        ck("write_shared", True)
    except Exception as e:
        print(f"  ❌ write_shared: {e}")
        import traceback; traceback.print_exc()
        ck("write_shared", False)
    finally:
        teardown(root)

    # ── 3. _format_private_memories ───
    try:
        from src.core.agent_factory import _format_private_memories
        mems = [
            {"type": "fact", "content": "竞品 B 定价比 A 低 30%"},
            {"type": "decision", "content": "调用 Read 读取竞品分析"},
            {"type": "reflection", "content": "学了 100 行新代码"},
        ]
        formatted = _format_private_memories(mems)
        assert "## 你的记忆" in formatted
        assert "📋" in formatted
        assert "🔧" in formatted
        assert "💭" in formatted
        assert "竞品 B" in formatted
        print(f"  ✅ private format: {len(formatted)} chars, tags correct")
        ck("private_format", True)
    except Exception as e:
        print(f"  ❌ private_format: {e}")
        ck("private_format", False)

    # ── 4. _format_shared_memories ────
    try:
        from src.core.agent_factory import _format_shared_memories
        mems = [
            {"type": "decision", "content": "团队决定：采用竞品 B 定价模式"},
            {"type": "fact", "content": "Q3 OKR: 完成核心功能上线"},
        ]
        formatted = _format_shared_memories(mems)
        assert "## 项目共识" in formatted
        assert "团队决定" in formatted
        assert "Q3 OKR" in formatted
        print(f"  ✅ shared format: {len(formatted)} chars, consensus section correct")
        ck("shared_format", True)
    except Exception as e:
        print(f"  ❌ shared_format: {e}")
        ck("shared_format", False)

    # ── 5. OnboardingMiddleware dual injection ──
    try:
        import src.core.store as store_mod
        store_mod._db = None
        await store_mod.get_db(":memory:")

        # Seed private + shared entries
        await store_mod.insert_memory(
            agent_id="product-manager", project_id="test",
            scope="private", type="fact", content="PD 的私有记忆",
        )
        await store_mod.insert_memory(
            agent_id="momo", project_id="test",
            scope="shared", type="decision", content="团队采用了方案 X",
        )

        from src.core.agent_factory import OnboardingMiddleware
        mw = OnboardingMiddleware(
            onboarding_context="项目背景",
            dashboard_dao=None,
            window_id="",
        )

        class FakeAgent:
            name = "product-manager"

        prompt = await mw.on_system_prompt(FakeAgent(), "base prompt")
        assert "## 项目背景" in prompt
        assert "## 你的记忆" in prompt
        assert "PD 的私有记忆" in prompt
        assert "## 项目共识" in prompt
        assert "团队采用了方案 X" in prompt
        print(f"  ✅ OnboardingMiddleware: private + shared sections rendered")
        await store_mod.close_db()
        ck("injection", True)
    except Exception as e:
        print(f"  ❌ injection: {e}")
        import traceback; traceback.print_exc()
        ck("injection", False)

    # ── 6. build_dashboard_tools includes WriteSharedMemory ──
    try:
        from src.core.dashboard_tools import build_dashboard_tools, WriteSharedMemoryTool
        from src.dao.dashboard_dao import DashboardDAO

        root = setup()
        dao = DashboardDAO(root)
        # momo tools
        momo_tools = build_dashboard_tools(
            dao=dao, dashboard_dao=dao,
            agent_id="momo", is_momo=True, window_id="w1",
        )
        names = [t.name for t in momo_tools]
        assert "write_shared_memory" in names, f"missing write_shared_memory in {names}"
        assert "create_task_plan" in names
        assert "update_dashboard" in names

        # non-momo tools
        pd_tools = build_dashboard_tools(
            dao=dao, dashboard_dao=dao,
            agent_id="product-manager", is_momo=False, window_id="w1",
        )
        pd_names = [t.name for t in pd_tools]
        assert "write_shared_memory" not in pd_names, f"PD should not get write_shared_memory, got {pd_names}"
        assert "create_task_plan" not in pd_names
        print(f"  ✅ toolkit: momo has {names}, PD has {pd_names}")
        ck("toolkit", True)
    except Exception as e:
        print(f"  ❌ toolkit: {e}")
        ck("toolkit", False)
    finally:
        teardown(root)

    # ── Report ───────────────────────
    print("=" * 50)
    passed = sum(1 for _, r in results if r == "✅")
    print(f"Results: {passed}/{len(results)}")
    for name, status in results:
        print(f"  {status} {name}")
    if passed < len(results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

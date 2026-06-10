"""Experiment: dashboard tools with OpenMoxToolBase constructors.

Run: cd backend && .venv/bin/python experiment/dashboard_tools_test.py
"""

import os, sys, shutil, tempfile, asyncio
from pathlib import Path

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BACKEND_DIR, "agentscope", "src"))
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from src.dao.dashboard_dao import DashboardDAO
from src.core.dashboard_tools import (
    UpdateDashboardTool, CreateTaskPlanTool, _has_cycle,
)


def setup():
    root = Path(tempfile.mkdtemp(prefix="mox_dt_"))
    (root / ".Project").mkdir(parents=True, exist_ok=True)
    (root / ".Agents").mkdir(parents=True, exist_ok=True)
    return root


def teardown(root: Path):
    if root.exists():
        shutil.rmtree(str(root), ignore_errors=True)


def _tk(dao, root, agent_id="product-manager", is_momo=False, window_id="w1"):
    """Shortcut: shared kwargs for OpenMoxToolBase subclasses."""
    return dict(
        dao=dao,  dashboard_dao=dao,   # dao IS the DashboardDAO in tests
        agent_id=agent_id, is_momo=is_momo, window_id=window_id,
    )


async def main():
    results = []

    def check(name, ok):
        results.append((name, "✅" if ok else "❌"))

    # ── 1. Owner update ──────────────
    try:
        root = setup()
        dao = DashboardDAO(root)
        t = dao.create_task(title="竞品分析", owner="product-manager")
        tool = UpdateDashboardTool(**_tk(dao, root, agent_id="product-manager"))
        result = await tool.__call__(task_id=t.id, status="in_progress")
        assert "→ in_progress" in result
        assert dao.get_task(t.id).status == "in_progress"
        print(f"  ✅ owner update: {result}")
        check("owner_update", True)
    except Exception as e:
        print(f"  ❌ owner_update: {e}")
        check("owner_update", False)
    finally:
        teardown(root)

    # ── 2. Non-owner denied ──────────
    try:
        root = setup()
        dao = DashboardDAO(root)
        t = dao.create_task(title="竞品分析", owner="product-manager")
        tool = UpdateDashboardTool(**_tk(dao, root, agent_id="dev-manager"))
        result = await tool.__call__(task_id=t.id, status="done")
        assert "权限拒绝" in result
        print(f"  ✅ non-owner denied: {result[:60]}...")
        check("non_owner", True)
    except Exception as e:
        print(f"  ❌ non_owner: {e}")
        check("non_owner", False)
    finally:
        teardown(root)

    # ── 3. Momo full access ──────────
    try:
        root = setup()
        dao = DashboardDAO(root)
        t = dao.create_task(title="竞品分析", owner="product-manager")
        tool = UpdateDashboardTool(**_tk(dao, root, agent_id="momo", is_momo=True))
        result = await tool.__call__(task_id=t.id, status="blocked", blocked_reason="等待资料")
        assert "→ blocked" in result
        assert "等待资料" in result
        print(f"  ✅ momo full access: {result}")
        check("momo_full", True)
    except Exception as e:
        print(f"  ❌ momo_full: {e}")
        check("momo_full", False)
    finally:
        teardown(root)

    # ── 4. Done propagation ──────────
    try:
        root = setup()
        dao = DashboardDAO(root)
        t1 = dao.create_task(title="A", owner="product-manager")
        t2 = dao.create_task(title="B", owner="dev-manager", depends_on=[t1.id])
        t3 = dao.create_task(title="C", owner="arch-manager", depends_on=[t2.id])
        tool_pd = UpdateDashboardTool(**_tk(dao, root, agent_id="product-manager"))
        result = await tool_pd.__call__(task_id=t1.id, status="done")
        print(f"    PD result: {result}")
        assert "done" in result.lower()
        tool_dev = UpdateDashboardTool(**_tk(dao, root, agent_id="dev-manager"))
        result2 = await tool_dev.__call__(task_id=t2.id, status="done")
        print(f"    Dev result: {result2}")
        assert "done" in result2.lower()
        print(f"  ✅ chain propagation: {result2}")
        check("propagation", True)
    except Exception as e:
        print(f"  ❌ propagation: {e}")
        check("propagation", False)
    finally:
        teardown(root)

    # ── 5. Nonexistent task ──────────
    try:
        root = setup()
        dao = DashboardDAO(root)
        tool = UpdateDashboardTool(**_tk(dao, root, agent_id="PD"))
        result = await tool.__call__(task_id="nonexistent", status="done")
        assert "不存在" in result
        print(f"  ✅ nonexistent: {result}")
        check("nonexistent", True)
    except Exception as e:
        print(f"  ❌ nonexistent: {e}")
        check("nonexistent", False)
    finally:
        teardown(root)

    # ── 6. CreateTaskPlan ────────────
    try:
        root = setup()
        dao = DashboardDAO(root)
        tool = CreateTaskPlanTool(**_tk(dao, root, agent_id="momo", is_momo=True))
        result = await tool.__call__(tasks=[
            {"title": "竞品分析", "phase": "research", "owner": "PD"},
            {"title": "demo 开发", "phase": "development", "owner": "Dev",
             "depends_on": ["竞品分析"]},
            {"title": "架构评审", "phase": "review", "owner": "Arch",
             "depends_on": ["demo 开发"], "window_id": None},
        ])
        assert "已创建 3 个任务" in result
        tasks = dao.get_all_tasks()
        assert len(tasks) == 3
        title_map = {t.title: t for t in tasks}
        assert title_map["demo 开发"].depends_on == [title_map["竞品分析"].id]
        assert title_map["架构评审"].window_id is None
        print(f"  ✅ batch create: {result}")
        check("create_plan", True)
    except Exception as e:
        print(f"  ❌ create_plan: {e}")
        check("create_plan", False)
    finally:
        teardown(root)

    # ── 7. Cycle rejection ───────────
    try:
        root = setup()
        dao = DashboardDAO(root)
        tool = CreateTaskPlanTool(**_tk(dao, root, agent_id="momo", is_momo=True))
        result = await tool.__call__(tasks=[
            {"title": "A", "owner": "PD", "depends_on": ["B"]},
            {"title": "B", "owner": "Dev", "depends_on": ["A"]},
        ])
        assert "循环" in result or "错误" in result
        assert dao.get_all_tasks() == []
        print(f"  ✅ cycle rejected: {result}")
        check("cycle_reject", True)
    except Exception as e:
        print(f"  ❌ cycle_reject: {e}")
        check("cycle_reject", False)
    finally:
        teardown(root)

    # ── 8-10. Cycle detection pure ───
    for name, deps, expected in [
        ("3-cycle", [("A",["C"]),("B",["A"]),("C",["B"])], True),
        ("linear",  [("A",[]),("B",["A"]),("C",["B"])], False),
        ("diamond", [("A",[]),("B",["A"]),("C",["A"]),("D",["B","C"])], False),
    ]:
        tasks = [{"title": t, "depends_on": d} for t, d in deps]
        result = _has_cycle(tasks)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {name}: cycle={result} (expected {expected})")
        check(f"cycle_{name}", result == expected)

    # ── 11. Partial dependency ───────
    try:
        root = setup()
        dao = DashboardDAO(root)
        dao.create_task_batch([
            {"title": "A"}, {"title": "B"}, {"title": "C", "depends_on": ["A", "B"]},
        ])
        tasks = dao.get_all_tasks()
        id_map = {t.title: t for t in tasks}
        dao.update_task(id_map["C"].id, depends_on=[id_map["A"].id, id_map["B"].id])
        dao.update_task(id_map["A"].id, status="done")
        succ = dao._get_unblocked_successors(id_map["A"].id)
        assert len(succ) == 0
        dao.update_task(id_map["B"].id, status="done")
        succ2 = dao._get_unblocked_successors(id_map["B"].id)
        assert len(succ2) == 1 and succ2[0].id == id_map["C"].id
        print(f"  ✅ partial dep: C unblocked only after both A&B done")
        check("partial_dep", True)
    except Exception as e:
        print(f"  ❌ partial_dep: {e}")
        check("partial_dep", False)
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

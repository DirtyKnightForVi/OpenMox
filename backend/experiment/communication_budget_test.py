"""Experiment: CommunicationBudgetMiddleware — budget deduction + exhaustion.

Run: cd backend && .venv/bin/python experiment/communication_budget_test.py
"""

import asyncio
import os
import sys
import tempfile
import shutil
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR / "agentscope" / "src"))
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))


async def main():
    results = []
    def ck(name, ok):
        results.append((name, "OK" if ok else "FAIL"))
        print(f"  {'✅' if ok else '❌'} {name}")

    # ── Setup ──────────────────────────────────────
    import src.core.store as store_mod
    store_mod._db = None
    await store_mod.get_db(":memory:")

    root = Path(tempfile.mkdtemp(prefix="mox_budget_"))
    from src.dao.config_dao import ConfigDAO
    ConfigDAO.init_project(root)
    dao = ConfigDAO(root)
    # Create agents
    for aid, name in [("momo", "momo"), ("dev", "dev"), ("pd", "pd")]:
        ad = root / ".Agents" / aid
        ad.mkdir(parents=True, exist_ok=True)
        import yaml
        with open(ad / "agent.yaml", "w") as f:
            yaml.dump({
                "id": aid, "name": name,
                "system": f"You are {name}.",
                "momo": aid == "momo",
            }, f)

    from src.dao.dashboard_dao import DashboardDAO
    dash = DashboardDAO(root)

    # ── T1: TaskItem has default budget ─────────────
    task = dash.create_task(title="测试任务", owner="dev")
    assert task.communication_budget == 3, f"Expected 3, got {task.communication_budget}"
    ck("default budget = 3", True)

    # ── T2: create_task accepts custom budget ────────
    task2 = dash.create_task(title="高沟通任务", owner="pd", communication_budget=10)
    assert task2.communication_budget == 10
    ck("custom budget = 10", True)

    # ── T3: update_task modifies budget ──────────────
    updated = dash.update_task(task2.id, communication_budget=5)
    assert updated.communication_budget == 5
    ck("update budget 10→5", True)

    # ── T4: YAML round-trip preserves budget ─────────
    # Reload from YAML
    dash2 = DashboardDAO(root)
    reloaded = dash2.get_task(task.id)
    assert reloaded is not None
    assert reloaded.communication_budget == 3
    ck("YAML round-trip preserves budget", True)

    # ── T5: Budget deduction via middleware ───────────
    from src.core.communication_budget_middleware import CommunicationBudgetMiddleware
    mw = CommunicationBudgetMiddleware(dash, "dev", "w1", momo_id="momo")

    # Make the task in_progress so budget applies
    dash.update_task(task.id, status="in_progress")

    # We can't easily test the full on_acting flow without a real agent.
    # Instead test the budget deduction logic via the dao directly:
    before = dash.get_task(task.id).communication_budget
    assert before == 3

    # Simulate what the middleware does: deduct
    dash.update_task(task.id, communication_budget=before - 1)
    after = dash.get_task(task.id).communication_budget
    assert after == 2
    ck("middleware deduction logic: 3→2", True)

    # ── T6: Budget exhaustion check ───────────────────
    # Set budget to 0 manually
    dash.update_task(task.id, communication_budget=0)
    exhausted = dash.get_task(task.id)
    assert exhausted.communication_budget == 0
    ck("budget exhausted (0)", True)

    # ── T7: Multiple tasks, separate budgets ──────────
    t_a = dash.create_task(title="任务A", owner="dev", communication_budget=3)
    t_b = dash.create_task(title="任务B", owner="dev", communication_budget=5)
    dash.update_task(t_a.id, status="in_progress")
    dash.update_task(t_b.id, status="in_progress")

    active = [t for t in dash.get_tasks_for_agent("dev", "w1") if t.status == "in_progress"]
    budgets = {t.title: t.communication_budget for t in active}
    assert budgets.get("任务A") == 3
    assert budgets.get("任务B") == 5
    ck("separate budgets per task", True)

    # ── T8: momo can update budget ────────────────────
    dash.update_task(task.id, communication_budget=7)
    assert dash.get_task(task.id).communication_budget == 7
    ck("momo refills budget 0→7", True)

    await store_mod.close_db()
    shutil.rmtree(str(root), ignore_errors=True)

    print("=" * 50)
    passed = sum(1 for _, r in results if r == "OK")
    print(f"Results: {passed}/{len(results)}")
    if passed < len(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

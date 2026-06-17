"""Experiment: DashboardDAO CRUD + filtering + edge cases.

Run: cd backend && .venv/bin/python experiment/dashboard_dao_test.py
"""

import os, sys, shutil, tempfile, time
from pathlib import Path

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BACKEND_DIR, "agentscope", "src"))
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from src.dao.dashboard_dao import DashboardDAO
from src.dao.models import TaskItem


# ── Fixture: temp project directory ──────────────

def setup():
    root = Path(tempfile.mkdtemp(prefix="mox_test_"))
    (root / ".Project").mkdir(parents=True, exist_ok=True)
    return root


def teardown(root: Path):
    if root.exists():
        shutil.rmtree(str(root), ignore_errors=True)


# ── Tests ────────────────────────────────────────

def test_create_and_read(tmpdir):
    """Create tasks → read back → fields correct."""
    dao = DashboardDAO(tmpdir)
    t = dao.create_task(title="竞品分析", owner="product-manager",
                        phase="research", window_id="w1", created_by="momo")
    assert t.id.startswith("task-"), f"bad id: {t.id}"
    assert t.status == "pending"
    assert t.created_by == "momo"

    # Read back
    loaded = dao.get_task(t.id)
    assert loaded is not None
    assert loaded.title == "竞品分析"
    assert loaded.phase == "research"
    print(f"  ✅ create+read: {t.id} '{t.title}' status={t.status}")


def test_batch_create(tmpdir):
    """Batch create with DAG edges."""
    dao = DashboardDAO(tmpdir)
    batch = [
        {"title": "A", "owner": "PD", "phase": "research"},
        {"title": "B", "owner": "Dev", "depends_on": [], "phase": "development"},
        {"title": "C", "owner": "Arch", "depends_on": [], "phase": "review", "window_id": None},
    ]
    created = dao.create_task_batch(batch, created_by="momo")
    assert len(created) == 3

    # DAG: B depends on A, C depends on B
    dao.update_task(created[1].id, depends_on=[created[0].id])
    dao.update_task(created[2].id, depends_on=[created[1].id])

    b = dao.get_task(created[1].id)
    c = dao.get_task(created[2].id)
    assert b.depends_on == [created[0].id]
    assert c.depends_on == [created[1].id]
    assert c.window_id is None
    print(f"  ✅ batch create: 3 tasks, DAG A←B←C valid")


def test_update_and_filtering(tmpdir):
    """Update task status + verify filtering."""
    dao = DashboardDAO(tmpdir)
    t1 = dao.create_task(title="PD task", owner="product-manager", window_id="w1")
    t2 = dao.create_task(title="Dev task", owner="dev-manager", window_id="w1")
    t3 = dao.create_task(title="Shared task", owner="arch-manager", window_id=None)

    # Filter for PD in w1
    visible = dao.get_tasks_for_agent("product-manager", "w1")
    ids = {t.id for t in visible}
    assert ids == {t1.id, t2.id, t3.id}, f"got {ids}"
    print(f"  ✅ PD in w1: {len(visible)} tasks visible")

    # Filter for Dev in w2 (different window)
    visible2 = dao.get_tasks_for_agent("dev-manager", "w2")
    ids2 = {t.id for t in visible2}
    assert t2.id in ids2, f"Dev's own task missing: {t2.id}"
    assert t3.id in ids2, f"project-level task missing: {t3.id}"
    print(f"  ✅ Dev in w2: {len(visible2)} tasks (own + project)")

    # Update t1 → done
    up = dao.update_task(t1.id, status="done", output="分析.md")
    assert up is not None
    assert up.status == "done"
    assert up.output == "分析.md"

    # Update nonexistent
    assert dao.update_task("nonexistent", status="done") is None
    print(f"  ✅ update: status + output, nonexistent → None")


def test_unblocked_successors(tmpdir):
    """When a task completes, check which successors become unblocked."""
    dao = DashboardDAO(tmpdir)
    t1 = dao.create_task(title="A", owner="PD")
    t2 = dao.create_task(title="B", owner="Dev")
    t3 = dao.create_task(title="C", owner="Arch")

    # B depends on A, C depends on B
    dao.update_task(t2.id, depends_on=[t1.id])
    dao.update_task(t3.id, depends_on=[t2.id])

    # A not done → no successors unblocked
    succ = dao._get_unblocked_successors(t1.id)
    assert len(succ) == 0, f"should be 0, got {len(succ)}"

    # A done → B unblocked
    dao.update_task(t1.id, status="done")
    succ = dao._get_unblocked_successors(t1.id)
    assert len(succ) == 1 and succ[0].id == t2.id
    print(f"  ✅ A done → B ({t2.id}) unblocked")

    # B still pending → C NOT unblocked (depends_on B not done)
    dao.update_task(t2.id, status="in_progress")
    succ2 = dao._get_unblocked_successors(t2.id)
    assert len(succ2) == 0
    print(f"  ✅ B in_progress → C still blocked")

    # B done → C unblocked
    dao.update_task(t2.id, status="done")
    succ3 = dao._get_unblocked_successors(t2.id)
    assert len(succ3) == 1 and succ3[0].id == t3.id
    print(f"  ✅ B done → C ({t3.id}) unblocked")


def test_yaml_persistence(tmpdir):
    """File round-trip: write DAO → read from raw file → fields match."""
    dao = DashboardDAO(tmpdir)
    dao.create_task(title="持久化测试", owner="PD", phase="research")
    dao.create_task(title="另一个", owner="Dev", depends_on=[], window_id=None)

    # Open a second DAO on the same dir (simulates process restart)
    dao2 = DashboardDAO(tmpdir)
    tasks = dao2.get_all_tasks()
    assert len(tasks) == 2
    assert tasks[0].title == "持久化测试"
    assert tasks[1].window_id is None
    print(f"  ✅ yaml persistence: 2 tasks survive DAO reload")


def test_empty_and_corrupted(tmpdir):
    """Empty file + corrupted YAML → safe defaults."""
    # Empty project
    dao = DashboardDAO(tmpdir)
    assert dao.get_all_tasks() == []
    assert dao.get_task("anything") is None
    assert dao.get_tasks_for_agent("PD", "w1") == []
    print(f"  ✅ empty project → all queries return safe defaults")

    # Corrupted YAML
    (tmpdir / ".Project" / "DASHBOARD.yaml").write_text(": not valid yaml [[[")
    dao2 = DashboardDAO(tmpdir)
    assert dao2.get_all_tasks() == []
    print(f"  ✅ corrupted YAML → [] no crash")


# ── Main ─────────────────────────────────────────

if __name__ == "__main__":
    results = []
    for name, fn in [
        ("create_read", test_create_and_read),
        ("batch_create", test_batch_create),
        ("update_filter", test_update_and_filtering),
        ("unblocked", test_unblocked_successors),
        ("yaml_persist", test_yaml_persistence),
        ("empty_corrupt", test_empty_and_corrupted),
    ]:
        root = setup()
        try:
            fn(root)
            results.append((name, "✅"))
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            import traceback; traceback.print_exc()
            results.append((name, f"❌ {e}"))
        finally:
            teardown(root)

    print("=" * 50)
    passed = sum(1 for _, r in results if r == "✅")
    print(f"Results: {passed}/{len(results)}")
    for name, status in results:
        print(f"  {status} {name}")
    if passed < len(results):
        sys.exit(1)

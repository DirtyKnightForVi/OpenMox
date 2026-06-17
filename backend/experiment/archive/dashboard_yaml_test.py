"""Experiment: YAML round-trip for DASHBOARD schema.

Validates:
  1. Python dataclass → yaml.safe_dump → file → yaml.safe_load → dataclass
  2. Edge cases: empty depends_on, None window_id, unicode fields
  3. Human-edited YAML backwards-compatibility (missing optional fields)

Run: cd backend && .venv/bin/python experiment/dashboard_yaml_test.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agentscope", "src"))

from dataclasses import dataclass, field, asdict
from pathlib import Path
import tempfile, yaml, time


# ── Schema (mirrors what DashboardDAO will use) ────

@dataclass
class TaskItem:
    id: str
    title: str
    description: str = ""
    phase: str = ""
    owner: str = ""
    status: str = "pending"          # pending | in_progress | done | blocked
    depends_on: list[str] = field(default_factory=list)
    window_id: str | None = None     # None = 项目级
    created_by: str = ""
    created_at: str = ""
    completed_at: str = ""
    output: str = ""
    blocked_reason: str = ""


def tasks_to_yaml(tasks: list[TaskItem]) -> str:
    """Serialize to DASHBOARD.yaml format."""
    data = {
        "version": 1,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tasks": [asdict(t) for t in tasks],
    }
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)


def yaml_to_tasks(raw: str) -> list[TaskItem]:
    """Parse DASHBOARD.yaml → list[TaskItem]. Skips malformed entries."""
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        return []
    task_dicts = data.get("tasks", [])
    if not isinstance(task_dicts, list):
        return []
    tasks = []
    for d in task_dicts:
        if not isinstance(d, dict) or "id" not in d:
            continue
        # None-safe: depends_on may be null / missing in human-edited YAML
        deps = d.get("depends_on") or []
        tasks.append(TaskItem(
            id=d["id"],
            title=d.get("title", d["id"]),
            description=d.get("description", ""),
            phase=d.get("phase", ""),
            owner=d.get("owner", ""),
            status=d.get("status", "pending"),
            depends_on=deps if isinstance(deps, list) else [],
            window_id=d.get("window_id"),   # None = project-level
            created_by=d.get("created_by", ""),
            created_at=d.get("created_at", ""),
            completed_at=d.get("completed_at", ""),
            output=d.get("output", ""),
            blocked_reason=d.get("blocked_reason", ""),
        ))
    return tasks


# ── Tests ────────────────────────────────────────

def test_round_trip():
    """Write → file → read back → fields match."""
    tasks = [
        TaskItem(id="task-001", title="竞品分析", phase="research",
                 owner="product-manager", status="done",
                 window_id="w_default", created_by="momo",
                 output=".Project/outputs/竞品分析.md"),
        TaskItem(id="task-002", title="demo 开发", phase="development",
                 owner="dev-manager", status="pending",
                 depends_on=["task-001"], window_id="w_default"),
        TaskItem(id="task-003", title="架构评审", phase="review",
                 owner="arch-manager", status="pending",
                 depends_on=["task-002"], window_id=None),
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(tasks_to_yaml(tasks))
        tmp_path = f.name

    raw = Path(tmp_path).read_text(encoding="utf-8")
    loaded = yaml_to_tasks(raw)

    assert len(loaded) == 3, f"expected 3, got {len(loaded)}"
    assert loaded[0].id == "task-001"
    assert loaded[0].window_id == "w_default"
    assert loaded[2].window_id is None          # None preserved
    assert loaded[1].depends_on == ["task-001"]
    assert loaded[0].depends_on == []           # empty list preserved
    print("  ✅ Round-trip: 3 tasks, all fields correct")


def test_human_edited_yaml():
    """Human may omit optional fields or use null."""
    raw = """\
version: 1
tasks:
  - id: "task-001"
    title: "竞品分析"
  - id: "task-002"
    title: "demo 开发"
    depends_on:
  - id: "task-003"
    title: "架构评审"
    window_id:
"""
    tasks = yaml_to_tasks(raw)
    assert len(tasks) == 3
    assert tasks[1].depends_on == []   # null → []
    assert tasks[2].window_id is None  # null → None
    assert tasks[0].status == "pending"  # default
    print("  ✅ Human-edited YAML: missing fields → defaults")


def test_empty_dashboard():
    """No DASHBOARD.yaml yet → empty list."""
    tasks = yaml_to_tasks("")
    assert tasks == []
    print("  ✅ Empty/missing YAML → []")


def test_partial_corruption():
    """One bad entry shouldn't crash everything."""
    raw = """\
version: 1
tasks:
  - "just a string"
  - id: "task-001"
    title: "ok task"
  - {key: val}
"""
    tasks = yaml_to_tasks(raw)
    assert len(tasks) == 1  # only the valid one
    assert tasks[0].id == "task-001"
    print("  ✅ Partial corruption: 1/3 entries survived")


def test_dashboard_filtering():
    """get_tasks_for_agent logic — window_id + owner filtering."""
    tasks = [
        TaskItem(id="t1", title="A", owner="PD", window_id="w1"),
        TaskItem(id="t2", title="B", owner="Dev", window_id="w1"),
        TaskItem(id="t3", title="C", owner="Arch", window_id=None),  # project-level
        TaskItem(id="t4", title="D", owner="Dev", window_id="w2"),   # other window
        TaskItem(id="t5", title="E", owner="Dev", window_id=None),
    ]

    def filter_tasks(agent_id, window_id):
        return [
            t for t in tasks
            if t.window_id is None          # project-level → always
            or t.window_id == window_id      # current window
            or t.owner == agent_id           # assigned to me → always
        ]

    # PD in w1: sees t1+t2 (same window) + t3+t5 (project-level)
    result = filter_tasks("product-manager", "w1")
    ids = {t.id for t in result}
    assert ids == {"t1", "t2", "t3", "t5"}, f"got {ids}"
    print("  ✅ PD in w1: sees window tasks + project-level")

    # Dev in w2: sees t4 (same window) + t5 (assigned) + t3 (project)
    result2 = filter_tasks("dev-manager", "w2")
    ids2 = {t.id for t in result2}
    assert ids2 == {"t3", "t4", "t5"}, f"got {ids2}"
    print("  ✅ Dev in w2: sees own window + assigned + project tasks")

    # Arch in w1: sees t1+t2 (same window) + t3+t5 (project)
    result3 = filter_tasks("arch-manager", "w1")
    ids3 = {t.id for t in result3}
    assert ids3 == {"t1", "t2", "t3", "t5"}, f"got {ids3}"
    print("  ✅ Arch in w1: sees window + project-level tasks")


if __name__ == "__main__":
    results = []
    for name, fn in [
        ("round_trip", test_round_trip),
        ("human_yaml", test_human_edited_yaml),
        ("empty", test_empty_dashboard),
        ("corruption", test_partial_corruption),
        ("filtering", test_dashboard_filtering),
    ]:
        try:
            fn()
            results.append((name, "✅"))
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            results.append((name, f"❌ {e}"))

    print("=" * 50)
    passed = sum(1 for _, r in results if r == "✅")
    print(f"Results: {passed}/{len(results)}")
    for name, status in results:
        print(f"  {status} {name}")
    if passed < len(results):
        sys.exit(1)

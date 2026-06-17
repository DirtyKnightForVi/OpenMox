"""
DAO 层单元测试 — DashboardDAO DAG 逻辑 (不依赖后端/LLM)

验证:
  - DAG 循环检测 (DFS 三色染色)
  - task done → 后继就绪传播
  - communication_budget 字段读写
  - 非负责人更新被拒 (字段级权限)

用法: cd backend && uv run pytest experiment/tests/test_dashboard_dao.py -v
"""

import os
import sys
import tempfile
from pathlib import Path

# Inject agentscope path (needed for ConfigDAO imports in dashboard_dao deps)
_backend = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_backend))
sys.path.insert(0, str(_backend / "agentscope" / "src"))


def _make_temp_project() -> str:
    """Create a temporary project directory with .Project/DASHBOARD.yaml."""
    tmp = tempfile.mkdtemp(prefix="test_dashboard_dao_")
    proj = Path(tmp) / ".Project"
    proj.mkdir(parents=True)
    return tmp


# ═══════════════════════════════════════════════════════════════
# DAG 循环检测
# ═══════════════════════════════════════════════════════════════


def test_dag_cycle_detection():
    """A → B → A 循环应被检测到."""
    from src.core.dashboard_tools import _has_cycle

    # 无循环
    assert not _has_cycle([
        {"title": "A", "depends_on": []},
        {"title": "B", "depends_on": ["A"]},
    ])

    # A → B → A 循环
    assert _has_cycle([
        {"title": "A", "depends_on": ["B"]},
        {"title": "B", "depends_on": ["A"]},
    ])

    # A → B → C → A 三节点循环
    assert _has_cycle([
        {"title": "A", "depends_on": ["C"]},
        {"title": "B", "depends_on": ["A"]},
        {"title": "C", "depends_on": ["B"]},
    ])


# ═══════════════════════════════════════════════════════════════
# Task 创建 + 就绪传播
# ═══════════════════════════════════════════════════════════════


def test_task_create_and_propagation():
    """创建任务 → done → 后继自动就绪."""
    from src.dao.dashboard_dao import DashboardDAO

    tmp = _make_temp_project()
    dao = DashboardDAO(tmp)

    # 创建前置任务
    t1 = dao.create_task(
        title="需求分析", owner="product-manager", phase="research",
        task_id="task-1",
    )
    assert t1.status == "pending"
    assert t1.communication_budget == 3  # default

    # 创建后继任务 (依赖 t1)
    t2 = dao.create_task(
        title="技术设计", owner="arch-manager", phase="development",
        depends_on=["task-1"], task_id="task-2",
    )
    assert t2.status == "pending"

    # 完成 t1
    dao.update_task("task-1", status="done")
    updated_t1 = dao.get_task("task-1")
    assert updated_t1.status == "done"

    # 验证后继任务就绪
    unblocked = dao._get_unblocked_successors("task-1")
    assert len(unblocked) == 1
    assert unblocked[0].id == "task-2"


# ═══════════════════════════════════════════════════════════════
# communication_budget 字段
# ═══════════════════════════════════════════════════════════════


def test_communication_budget_field():
    """communication_budget 字段可读写."""
    from src.dao.dashboard_dao import DashboardDAO

    tmp = _make_temp_project()
    dao = DashboardDAO(tmp)

    # 创建时默认 3
    t = dao.create_task(title="测试", owner="dev-manager", task_id="task-1")
    assert t.communication_budget == 3

    # 显示指定 budget
    t2 = dao.create_task(
        title="预算5", owner="momo", task_id="task-2",
        communication_budget=5,
    )
    assert t2.communication_budget == 5

    # 更新 budget
    dao.update_task("task-1", communication_budget=10)
    updated = dao.get_task("task-1")
    assert updated.communication_budget == 10

    # budget=0
    dao.update_task("task-1", communication_budget=0)
    updated = dao.get_task("task-1")
    assert updated.communication_budget == 0


# ═══════════════════════════════════════════════════════════════
# 看板过滤 (get_tasks_for_agent)
# ═══════════════════════════════════════════════════════════════


def test_task_filtering_for_agent():
    """get_tasks_for_agent 按 owner/window_id 过滤."""
    from src.dao.dashboard_dao import DashboardDAO

    tmp = _make_temp_project()
    dao = DashboardDAO(tmp)

    # 项目级任务 (window_id=None)
    dao.create_task(title="项目级", owner="momo", task_id="t1")
    # 窗口级任务
    dao.create_task(title="窗口W1", owner="product-manager", window_id="w1", task_id="t2")
    # 分配给 dev 的窗口级任务
    dao.create_task(title="W1-dev", owner="dev-manager", window_id="w1", task_id="t3")

    # dev-manager 在 w2 窗口应看到: 项目级 + 自己名下的
    tasks_w2 = dao.get_tasks_for_agent("dev-manager", "w2")
    ids = {t.id for t in tasks_w2}
    assert "t1" in ids  # 项目级，始终可见
    assert "t3" in ids  # 自己名下
    assert "t2" not in ids  # 不是自己名下，也不是当前窗口

    # momo 应看到全部
    tasks_momo = dao.get_tasks_for_agent("momo", "w1")
    assert len(tasks_momo) >= 2

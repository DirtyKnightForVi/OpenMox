"""
Dashboard REST API — read project task DAG, update tasks (human-in-the-loop).

Endpoints:
  GET  /api/dashboard?window_id=...&project_path=...
       → visible tasks for the given window, grouped by phase
  PATCH /api/dashboard/{task_id}
       → update task fields (human has full permission)
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from pathlib import Path

from ..dao.dashboard_dao import DashboardDAO

router = APIRouter(prefix="/api", tags=["dashboard"])


class TaskUpdate(BaseModel):
    status: str | None = None
    title: str | None = None
    description: str | None = None
    phase: str | None = None
    owner: str | None = None
    output: str | None = None
    blocked_reason: str | None = None


@router.get("/dashboard")
async def get_dashboard(
    window_id: str = Query(default="", description="Window ID to filter by"),
    project_path: str = Query(default=".", description="Project root path"),
):
    """Return tasks visible in *window_id* grouped by phase."""
    dao = DashboardDAO(project_path)
    tasks = dao.get_all_tasks()

    # Filter by window
    if window_id:
        tasks = [t for t in tasks if t.window_id is None or t.window_id == window_id]

    # Group by phase
    by_phase: dict[str, list[dict]] = {}
    for t in tasks:
        phase = t.phase or "未分类"
        by_phase.setdefault(phase, []).append({
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "phase": t.phase,
            "owner": t.owner,
            "status": t.status,
            "depends_on": t.depends_on,
            "window_id": t.window_id,
            "created_by": t.created_by,
            "created_at": t.created_at,
            "completed_at": t.completed_at,
            "output": t.output,
            "blocked_reason": t.blocked_reason,
        })

    return {"phases": by_phase, "total": len(tasks)}


@router.get("/dashboard/tasks/{agent_id}")
async def get_agent_task_context(
    agent_id: str,
    window_id: str = Query(default="", description="Window ID"),
    project_path: str = Query(default=".", description="Project root path"),
):
    """Return the agent's TaskContext (plan-execute queue) + DASHBOARD tasks.

    The TaskContext lives in Redis (AgentState.tasks_context) and shows
    the worker's real-time execution plan with head/tail auto-injected.
    The DASHBOARD tasks show project-level task metadata.
    """
    from main import app as _app
    import hashlib

    storage = getattr(_app.state, "storage", None)
    if not storage:
        return {"tasks": [], "dashboard_tasks": []}

    project_hash = hashlib.md5(project_path.encode()).hexdigest()[:8]
    user_id = f"openmox:{project_hash}"
    session_id = f"{window_id}:{agent_id}"

    result = {"tasks": [], "dashboard_tasks": []}

    # Read TaskContext from Redis session state
    try:
        sess = await storage.get_session(user_id, agent_id, session_id)
        if sess and sess.state and sess.state.tasks_context:
            for t in sess.state.tasks_context.tasks:
                result["tasks"].append({
                    "id": t.id,
                    "subject": t.subject,
                    "description": t.description[:200] if t.description else "",
                    "state": t.state,
                    "metadata": t.metadata,
                })
    except Exception:
        pass

    # Read DASHBOARD tasks for this agent
    try:
        dao = DashboardDAO(project_path)
        dash_tasks = dao.get_tasks_for_agent(agent_id, window_id)
        for dt in dash_tasks:
            result["dashboard_tasks"].append({
                "id": dt.id,
                "title": dt.title,
                "status": dt.status,
                "phase": dt.phase,
                "owner": dt.owner,
                "output": dt.output,
                "depends_on": dt.depends_on,
                "communication_budget": dt.communication_budget,
            })
    except Exception:
        pass

    return result


@router.patch("/dashboard/{task_id}")
async def update_task(
    task_id: str,
    body: TaskUpdate,
    project_path: str = Query(default=".", description="Project root path"),
):
    """Update a task. Human has full permission (no ownership check)."""
    dao = DashboardDAO(project_path)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"ok": False, "error": "no fields to update"}

    updated = dao.update_task(task_id, **updates)
    if not updated:
        return {"ok": False, "error": f"task '{task_id}' not found"}

    return {
        "ok": True,
        "task": {
            "id": updated.id,
            "title": updated.title,
            "status": updated.status,
            "owner": updated.owner,
        },
    }

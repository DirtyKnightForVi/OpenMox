"""
DashboardDAO — project-level task DAG persistence.

Reads/writes .Project/DASHBOARD.yaml.  All tasks are stored in one flat
list with DAG edges expressed via ``depends_on`` (list of task IDs).

Filtering (get_tasks_for_agent) applies three rules:
  1. window_id is None       → project-level, always visible
  2. window_id == current     → same window, visible
  3. owner == agent_id        → assigned to me, always visible
"""

import time
import uuid
import yaml
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .models import TaskItem


class DashboardDAO:
    """CRUD + filtering for the DASHBOARD.yaml task DAG."""

    def __init__(self, project_root: str | Path):
        self.root = Path(project_root)
        self._path = self.root / ".Project" / "DASHBOARD.yaml"

    # ═══════════════════════════════════════════════════
    # Read
    # ═══════════════════════════════════════════════════

    def get_all_tasks(self) -> list[TaskItem]:
        """Return every task in the dashboard, unsorted."""
        return self._load()

    def get_task(self, task_id: str) -> Optional[TaskItem]:
        """Return a single task by id, or None."""
        for t in self._load():
            if t.id == task_id:
                return t
        return None

    def get_tasks_for_agent(
        self, agent_id: str, window_id: str,
    ) -> list[TaskItem]:
        """Return tasks visible to *agent_id* in *window_id*.

        Rules (OR logic, any match = visible):
        - window_id is None   (project-level)
        - window_id matches   (same window)
        - owner == agent_id   (assigned to me)
        """
        all_tasks = self._load()
        return [
            t for t in all_tasks
            if t.window_id is None
            or t.window_id == window_id
            or t.owner == agent_id
        ]

    # ═══════════════════════════════════════════════════
    # Write
    # ═══════════════════════════════════════════════════

    def create_task(
        self,
        *,
        title: str,
        owner: str = "",
        description: str = "",
        phase: str = "",
        depends_on: Optional[list[str]] = None,
        window_id: Optional[str] = None,
        created_by: str = "",
        task_id: Optional[str] = None,
        communication_budget: int = 3,
    ) -> TaskItem:
        """Create a single task and persist. Returns the new TaskItem."""
        tasks = self._load()
        new_id = task_id or f"task-{uuid.uuid4().hex[:8]}"
        now = time.strftime("%Y-%m-%dT%H:%M:%S")

        item = TaskItem(
            id=new_id,
            title=title,
            description=description,
            phase=phase,
            owner=owner,
            status="pending",
            depends_on=list(depends_on or []),
            window_id=window_id,
            created_by=created_by,
            created_at=now,
            communication_budget=communication_budget,
        )
        tasks.append(item)
        self._save(tasks)
        return item

    def create_task_batch(
        self,
        tasks: list[dict],
        *,
        created_by: str = "",
    ) -> list[TaskItem]:
        """Create multiple tasks atomically. Returns the created items.

        Each dict in *tasks* must have at least ``title``.
        Optional keys: description, phase, owner, depends_on, window_id.
        """
        existing = self._load()
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        created: list[TaskItem] = []

        for t in tasks:
            new_id = f"task-{uuid.uuid4().hex[:8]}"
            item = TaskItem(
                id=new_id,
                title=t["title"],
                description=t.get("description", ""),
                phase=t.get("phase", ""),
                owner=t.get("owner", ""),
                status="pending",
                depends_on=list(t.get("depends_on") or []),
                window_id=t.get("window_id"),
                created_by=created_by,
                created_at=now,
                communication_budget=t.get("communication_budget", 3),
            )
            existing.append(item)
            created.append(item)

        self._save(existing)
        return created

    def update_task(self, task_id: str, **updates) -> Optional[TaskItem]:
        """Update fields of an existing task. Returns the updated item.

        Accepted keys: status, title, description, phase, owner, output,
                       blocked_reason, completed_at, window_id, depends_on.
        Unknown keys are silently ignored.
        """
        tasks = self._load()
        allowed = {
            "status", "title", "description", "phase", "owner",
            "output", "blocked_reason", "completed_at", "window_id",
            "depends_on", "communication_budget",
        }
        for i, t in enumerate(tasks):
            if t.id == task_id:
                for key, val in updates.items():
                    if key in allowed and hasattr(t, key):
                        setattr(t, key, val)
                self._save(tasks)
                return t
        return None

    def _get_unblocked_successors(self, task_id: str) -> list[TaskItem]:
        """Return tasks whose depends_on are ALL done after *task_id* is done.

        Used by UpdateDashboard tool for readiness propagation.
        """
        tasks = self._load()
        unblocked: list[TaskItem] = []
        for t in tasks:
            if task_id in t.depends_on:
                if all(
                    (dep_t := self.get_task(dep)) and dep_t.status == "done"
                    for dep in t.depends_on
                ):
                    unblocked.append(t)
        return unblocked

    # ═══════════════════════════════════════════════════
    # Internal
    # ═══════════════════════════════════════════════════

    def _load(self) -> list[TaskItem]:
        """Parse DASHBOARD.yaml → list[TaskItem].

        Returns [] if file missing, empty, or malformed.
        Individual malformed entries are skipped.
        """
        if not self._path.exists():
            return []
        try:
            raw = self._path.read_text(encoding="utf-8")
        except Exception:
            return []
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError:
            return []
        if not isinstance(data, dict):
            return []
        task_dicts = data.get("tasks")
        if not isinstance(task_dicts, list):
            return []

        result: list[TaskItem] = []
        for d in task_dicts:
            if not isinstance(d, dict) or "id" not in d:
                continue
            deps = d.get("depends_on") or []
            result.append(TaskItem(
                id=str(d["id"]),
                title=str(d.get("title", d["id"])),
                description=str(d.get("description", "")),
                phase=str(d.get("phase", "")),
                owner=str(d.get("owner", "")),
                status=str(d.get("status", "pending")),
                depends_on=list(deps) if isinstance(deps, list) else [],
                window_id=d.get("window_id"),
                created_by=str(d.get("created_by", "")),
                created_at=str(d.get("created_at", "")),
                completed_at=str(d.get("completed_at", "")),
                output=str(d.get("output", "")),
                blocked_reason=str(d.get("blocked_reason", "")),
                communication_budget=int(d.get("communication_budget", 3)),
            ))
        return result

    def _save(self, tasks: list[TaskItem]) -> None:
        """Serialize list[TaskItem] → DASHBOARD.yaml."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tasks": [asdict(t) for t in tasks],
        }
        with open(self._path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                data, f, allow_unicode=True, sort_keys=False,
                default_flow_style=False,
            )

"""
Dashboard tools — UpdateDashboard + CreateTaskPlan + DAG cycle detection.

All agents get UpdateDashboard (field-level permission inside __call__).
Only momo gets CreateTaskPlan (batch create + cycle check).
"""

from typing import Any

from agentscope.permission import PermissionContext, PermissionDecision, PermissionBehavior

from .openmox_tool_base import OpenMoxToolBase


# ═══════════════════════════════════════════════════════════════════
# Cycle detection (DFS three-color)
# ═══════════════════════════════════════════════════════════════════

def _has_cycle(tasks: list[dict]) -> bool:  # (unchanged)
    """Return True if the proposed task DAG contains a cycle."""
    titles = {t["title"] for t in tasks}
    adj: dict[str, list[str]] = {}
    for t in tasks:
        deps = [d for d in (t.get("depends_on") or []) if d in titles]
        adj[t["title"]] = deps

    color: dict[str, int] = {title: 0 for title in titles}

    def dfs(node: str) -> bool:
        color[node] = 1
        for neighbor in adj.get(node, []):
            if color[neighbor] == 1:
                return True
            if color[neighbor] == 0 and dfs(neighbor):
                return True
        color[node] = 2
        return False

    for title in titles:
        if color[title] == 0 and dfs(title):
            return True
    return False


# ═══════════════════════════════════════════════════════════════════
# UpdateDashboard tool
# ═══════════════════════════════════════════════════════════════════

class UpdateDashboardTool(OpenMoxToolBase):
    """Update a task's status, output, or blocked reason.

    Field-level permission (inside __call__, using self._agent_id):
      - Task owner → status, output, blocked_reason
      - momo       → any field (including communication_budget)
      - others     → denied
    """

    name: str = "update_dashboard"
    description: str = (
        "更新项目看板中一个任务的状态。设为 done 时会自动通知你哪些后续任务已就绪。"
        "参数: task_id(必需), status(pending|in_progress|done|blocked), "
        "output(文件路径), blocked_reason(阻塞原因), "
        "communication_budget(momo专用, 调整任务通信预算)。"
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "要更新的任务 ID",
            },
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "done", "blocked"],
                "description": "新状态",
            },
            "output": {
                "type": "string",
                "description": "完成时输出的文件路径（仅 status=done 时有意义）",
            },
            "blocked_reason": {
                "type": "string",
                "description": "阻塞原因（仅 status=blocked 时有意义）",
            },
            "communication_budget": {
                "type": "integer",
                "description": "调整任务通信预算（仅 momo 可操作）",
            },
        },
        "required": ["task_id"],
    }
    is_concurrency_safe: bool = True
    is_read_only: bool = False

    async def __call__(
        self,
        task_id: str,
        status: str = "",
        output: str = "",
        blocked_reason: str = "",
        communication_budget: int | None = None,
    ) -> str:
        task = self._dashboard_dao.get_task(task_id)
        if not task:
            return f"[错误] 任务 '{task_id}' 不存在"

        # ── Field-level permission ──────────────────
        is_owner = (self._agent_id == task.owner)
        if not is_owner and not self._is_momo:
            return (
                f"[权限拒绝] 任务 '{task.title}' 不归你负责。"
                f"只有任务负责人({task.owner})或 momo 可以更新。"
            )

        updates: dict[str, Any] = {}
        if status:
            updates["status"] = status
        if output:
            updates["output"] = output
        if blocked_reason:
            updates["blocked_reason"] = blocked_reason
        if communication_budget is not None:
            updates["communication_budget"] = communication_budget

        if not self._is_momo:
            allowed = {"status", "output", "blocked_reason"}
            disallowed = set(updates) - allowed
            if disallowed:
                return f"[权限拒绝] 你只能更新任务状态/输出/阻塞原因，不能改 {disallowed}"

        updated = self._dashboard_dao.update_task(task_id, **updates)
        if not updated:
            return f"[错误] 更新任务 '{task_id}' 失败"

        lines = [f"任务 '{updated.title}' → {updated.status}"]
        if communication_budget is not None:
            lines.append(f"通信预算已调整为 {communication_budget}")
        if updated.status == "done":
            unblocked = self._dashboard_dao._get_unblocked_successors(task_id)
            if unblocked:
                names = ", ".join(
                    f"@{t.owner} → {t.title}" for t in unblocked
                )
                lines.append(f"以下任务已就绪：{names}")
        elif updated.status == "blocked" and blocked_reason:
            lines.append(f"阻塞原因：{blocked_reason}")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# CreateTaskPlan tool (momo only via registration, not inheritance)
# ═══════════════════════════════════════════════════════════════════

class CreateTaskPlanTool(OpenMoxToolBase):
    """Batch create tasks with DAG dependencies. momo only."""

    name: str = "create_task_plan"
    description: str = (
        "批量创建项目任务，可指定阶段、负责人、前置依赖和通信预算。"
        "任务之间通过 depends_on 形成依赖链（DAG）。"
        "参数 tasks 是一个数组，每个元素含: title(必需), description, phase, owner, depends_on(任务标题列表), window_id, communication_budget(默认3)。"
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title":       {"type": "string", "description": "任务名称"},
                        "description": {"type": "string", "description": "任务简述"},
                        "phase":       {"type": "string", "description": "阶段: research | development | review | delivery"},
                        "owner":       {"type": "string", "description": "负责人 agent_id"},
                        "depends_on":  {"type": "array", "items": {"type": "string"}, "description": "前置任务的标题列表"},
                        "window_id":   {"type": "string", "description": "关联窗口 ID，null 表示项目级"},
                        "communication_budget": {"type": "integer", "description": "任务通信预算，默认 3"},
                    },
                    "required": ["title"],
                },
                "description": "任务列表",
            },
        },
        "required": ["tasks"],
    }
    is_concurrency_safe: bool = False
    is_read_only: bool = False

    async def __call__(self, tasks: list[dict]) -> str:
        if not tasks:
            return "[错误] tasks 不能为空"

        if _has_cycle(tasks):
            return (
                "[错误] 任务依赖中存在循环引用（例如 A→B→A）。"
                "请检查 depends_on 字段并重新排列。"
            )

        created = self._dashboard_dao.create_task_batch(tasks, created_by="momo")
        title_to_id = {t.title: t.id for t in created}

        for item, raw in zip(created, tasks):
            deps = raw.get("depends_on") or []
            dep_ids = [title_to_id[d] for d in deps if d in title_to_id]
            if dep_ids:
                self._dashboard_dao.update_task(item.id, depends_on=dep_ids)

        summary = "\n".join(
            f"  · {t.id} {t.title} → @{t.owner} [{t.phase or '未指定阶段'}]"
            for t in created
        )
        return f"已创建 {len(created)} 个任务：\n{summary}"


# ═══════════════════════════════════════════════════════════════════
# WriteSharedMemory tool (momo only)
# ═══════════════════════════════════════════════════════════════════

class WriteSharedMemoryTool(OpenMoxToolBase):
    """Write a project-wide consensus entry into shared memory.  momo only."""

    name: str = "write_shared_memory"
    description: str = (
        "将一条项目级别的共识、决策或结论写入共同记忆（所有团队成员都可见）。"
        "参数: content(记忆内容), type(fact|decision|preference|context), importance(0-1 重要性)。"
        "仅当你确认某个结论是团队共识时才使用。个人工作记录请勿写入。"
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "记忆内容。用简洁的中文描述共识内容。",
            },
            "type": {
                "type": "string",
                "enum": ["fact", "decision", "preference", "context"],
                "description": "记忆类型",
            },
            "importance": {
                "type": "number",
                "description": "重要性 0-1，默认 0.8。关键决策用 0.9+。",
            },
        },
        "required": ["content"],
    }
    is_concurrency_safe: bool = True
    is_read_only: bool = False

    async def check_permissions(
        self,
        tool_input: dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        if not self._is_momo:
            return PermissionDecision(
                behavior=PermissionBehavior.DENY,
                message="只有 momo 可以写入共同记忆",
            )
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="momo 允许写入共同记忆",
        )

    async def __call__(
        self,
        content: str,
        type: str = "decision",
        importance: float = 0.8,
    ) -> str:
        """Write a shared memory entry."""
        try:
            from ..core import store as mem_store
            await mem_store.insert_memory(
                agent_id="momo",  # momo acts as the scribe
                project_id=str(self._dao.root),
                scope="shared",
                type=type,
                content=content,
                source=f"momo:{self._window_id}",
                importance=importance,
            )
            return f"共同记忆已写入：{content[:80]}..."
        except Exception as e:
            return f"[错误] 写入共同记忆失败：{e}"


# ═══════════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════════

def build_dashboard_tools(
    *,
    storage: object,          # OpenMoxStorage
    message_bus: object,      # OpenMoxMessageBus
    agent_id: str = "",
    is_momo: bool = False,
    window_id: str = "",
    project_root: str = "",
) -> list:
    """Return dashboard tools for one agent.

    Every agent gets UpdateDashboard.
    Only momo gets CreateTaskPlan + WriteSharedMemory.

    Args:
        project_root: Absolute path to the project directory. If provided,
                      tools get a project-scoped DashboardDAO so they write
                      to the correct DASHBOARD.yaml.
    """
    kwargs = dict(
        storage=storage,
        message_bus=message_bus,
        user_id="openmox",
        session_id=window_id,
        agent_id=agent_id,
        is_momo=is_momo,
        project_root=project_root,
    )
    tools = [UpdateDashboardTool(**kwargs)]
    if is_momo:
        tools.append(CreateTaskPlanTool(**kwargs))
        tools.append(WriteSharedMemoryTool(**kwargs))
    return tools

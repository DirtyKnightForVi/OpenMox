"""
OpenMoxChatService — ChatService subclass that filters out AgentScope
built-in tools that conflict with our design:

Removed from leader toolkit:
  - AgentCreate   — creates ephemeral Redis workers; our design uses
                    YAML templates + SubAgentTemplate mapping
  - AgentInvite   — invites existing agents to teams; our design manages
                    team membership via .Project/team.yaml
  - TeamCreate    — AgentScope's team management; our design manages
                    teams per-project via .Project/team.yaml
  - TaskCreate / TaskList / TaskGet / TaskUpdate
                  — AgentScope's built-in planning tools that don't
                    know about DASHBOARD.yaml; our equivalents are
                    create_task_plan / update_dashboard

Kept:
  - TeamSay       — inter-agent communication (core to our design)
  - TeamDelete    — safe to keep (won't be used without TeamCreate)
  - Schedule*     — retained; agentscope cron scheduling (non-conflicting)
  - ToolStop      — retained; offloaded tool cancellation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentscope.app._service._chat import ChatService
from agentscope.app._service._toolkit import get_toolkit
from agentscope.state import Task, TaskContext

if TYPE_CHECKING:
    from agentscope.app.storage import StorageBase
    from agentscope.app.message_bus import MessageBus
    from agentscope.app._types import (
        AgentToolFactory,
        AgentMiddlewareFactory,
        EventProjector,
        SubAgentTemplate,
    )
    from agentscope.app._manager import (
        SchedulerManager,
        BackgroundTaskManager,
        ChatRunRegistry,
    )
    from agentscope.app.workspace_manager import WorkspaceManagerBase


# Tools that AgentScope injects automatically but we DON'T want.
# These conflict with our YAML-based agent management and dashboard system.
_UNWANTED_TOOLS: set[str] = {
    "AgentCreate",      # ephemeral Redis worker → use YAML templates
    "AgentInvite",      # invite agents to team → use .Project/team.yaml
    "TeamCreate",       # AgentScope team → use .Project/team.yaml
    # TaskCreate/TaskList/TaskGet/TaskUpdate are KEPT — workers use them
    # for the plan-execute loop (TaskContext auto-injected by _run_one).
}


class OpenMoxChatService(ChatService):
    """ChatService that filters out unwanted AgentScope built-in tools."""

    def __init__(
        self,
        *,
        storage: "StorageBase",
        workspace_manager: "WorkspaceManagerBase",
        scheduler_manager: "SchedulerManager",
        background_task_manager: "BackgroundTaskManager",
        message_bus: "MessageBus",
        extra_agent_tools: "AgentToolFactory | None" = None,
        extra_agent_middlewares: "AgentMiddlewareFactory | None" = None,
        extra_projectors: "list[EventProjector] | None" = None,
        custom_subagent_templates: "dict[str, SubAgentTemplate] | None" = None,
    ) -> None:
        super().__init__(
            storage=storage,
            workspace_manager=workspace_manager,
            scheduler_manager=scheduler_manager,
            background_task_manager=background_task_manager,
            message_bus=message_bus,
            extra_agent_tools=extra_agent_tools,
            extra_agent_middlewares=extra_agent_middlewares,
            extra_projectors=extra_projectors,
            custom_subagent_templates=custom_subagent_templates,
        )

    async def _run_impl(
        self,
        user_id: str,
        session_id: str,
        agent_id: str,
        input_msg,
    ) -> None:
        """Override: filter toolkit after assembly, then delegate to parent.

        The parent's _run_impl calls get_toolkit() internally.  We can't
        intercept that call without copying the entire ~250-line method.
        Instead, we monkey-patch get_toolkit for the duration of this call
        so the returned toolkit has unwanted tools stripped.
        """
        import agentscope.app._service._chat as _chat_module

        _original = _chat_module.get_toolkit

        async def _filtered_get_toolkit(**kwargs):
            toolkit = await _original(**kwargs)

            # Filter unwanted tools
            for group in toolkit.tool_groups:
                group.tools = [
                    t for t in (group.tools or [])
                    if t.name not in _UNWANTED_TOOLS
                ]

            # ── Seed TaskContext (plan-execute model) ──
            # This runs BEFORE the agent is assembled (step 3 of _run_impl),
            # so the agent will see the seeded tasks in its state.
            # Covers both user-initiated runs AND WakeupDispatcher wake-ups.
            try:
                session_record = kwargs.get("session_record")
                agent_record = kwargs.get("agent_record")
                if session_record and agent_record and session_record.state:
                    await _seed_tasks_in_state(
                        session_record=session_record,
                        agent_record=agent_record,
                    )
            except Exception:
                pass

            return toolkit

        _chat_module.get_toolkit = _filtered_get_toolkit
        try:
            await super()._run_impl(user_id, session_id, agent_id, input_msg)
        finally:
            _chat_module.get_toolkit = _original


async def _seed_tasks_in_state(
    *,
    session_record,
    agent_record,
) -> None:
    """Inject plan-execute TaskContext into session state.

    Called from the monkey-patched get_toolkit, which runs for EVERY
    agent invocation (user-initiated AND WakeupDispatcher wake-ups).
    """
    session_id = session_record.id
    agent_id = agent_record.id

    # Extract window_id: "{window_id}:{agent_id}"
    window_id = session_id.rsplit(":", 1)[0] if ":" in session_id else session_id

    # Resolve project_path from WebSocket registry
    project_path = "."
    try:
        from .ws_registry import get_project_path
        # Try full session_id first, then bare window_id
        pp = await get_project_path(session_id)
        if not pp:
            pp = await get_project_path(window_id)
        if pp:
            project_path = pp
    except Exception:
        pass

    if project_path == ".":
        return  # Can't seed without project context

    # Read DASHBOARD tasks assigned to this agent
    try:
        from ..dao.dashboard_dao import DashboardDAO
        dd = DashboardDAO(project_path)
        dash_tasks = dd.get_tasks_for_agent(agent_id, window_id)
    except Exception:
        return

    if not dash_tasks:
        return

    tasks: list = []

    # Head: claim + report_to_group
    pending_titles = ", ".join(t.title for t in dash_tasks if t.status == "pending")
    tasks.append(Task(
        subject="📢 认领并汇报任务",
        description=(
            f"📢 向群聊汇报：调用 report_to_group 告知你已经认领了以下任务并开始工作："
            f"{pending_titles or '任务'}。"
            f"同时调用 update_dashboard 将任务状态更新为 in_progress。"
        ),
        state="pending",
        metadata={"type": "report", "action": "claim"},
    ))

    # Middle: DASHBOARD tasks
    for dt in dash_tasks:
        tasks.append(Task(
            subject=dt.title,
            description=dt.description or f"执行任务: {dt.title}",
            state="pending" if dt.status != "done" else "completed",
            metadata={"dashboard_id": dt.id},
        ))

    # Tail: completion report
    tasks.append(Task(
        subject="📢 完成汇报",
        description=(
            "📢 所有任务完成后，调用 report_to_group 向群聊发送完整的成果汇报。"
            "然后调用 update_dashboard 将已完成的任务标记为 done。"
        ),
        state="pending",
        metadata={"type": "report", "action": "complete"},
    ))

    # Merge with existing TaskContext to preserve completed states
    existing = session_record.state.tasks_context
    if existing and existing.tasks:
        old_map = {t.subject: t for t in existing.tasks}
        for t in tasks:
            old = old_map.get(t.subject)
            if old and old.state == "completed":
                t.state = "completed"

    session_record.state.tasks_context = TaskContext(tasks=tasks)

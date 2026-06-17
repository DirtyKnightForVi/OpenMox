"""
AgentScope Agent factory — model singleton + OnboardingMiddleware.

Key design:
  - One OpenAIChatModel shared across all agents (DeepSeek).
  - Agent instances are now created by ChatService._run_impl — no more global cache.
  - OnboardingMiddleware injects project background, dashboard, and memory
    into system_prompt at reply time.

The global Agent cache is REMOVED — each ChatService._run_impl call creates
a fresh Agent with its own AgentState, eliminating the context isolation issue.
"""

from typing import Optional

from agentscope.agent import Agent
from agentscope.model import OpenAIChatModel
from agentscope.credential import OpenAICredential
from agentscope.middleware import MiddlewareBase

from .settings import get_settings
from .logging import get_logger

log = get_logger(__name__)

# ── Model singleton ────────────────────────────────────

_model: Optional[OpenAIChatModel] = None


def get_model() -> OpenAIChatModel:
    """Return the shared DeepSeek model instance (lazy singleton)."""
    global _model
    if _model is None:
        s = get_settings()
        _model = OpenAIChatModel(
            credential=OpenAICredential(
                api_key=s.deepseek_api_key,
                base_url=s.deepseek_base_url,
            ),
            model=s.deepseek_model,
        )
        log.info(
            "Model ready: %s @ %s",
            s.deepseek_model,
            s.deepseek_base_url,
        )
    return _model


# ── Minimal Agent helper (no cache — each call fresh) ─

# Legacy: scheduler.py and call_agent.py still use this.
# ChatService is the primary path; this is for direct Agent invocation.
# No caching — each call creates a fresh Agent with new AgentState.

def get_agent(
    agent_id: str,
    system_prompt: str,
    *,
    middlewares: Optional[list[MiddlewareBase]] = None,
    extra_tools: Optional[list] = None,
    skill_dirs: Optional[list[str]] = None,
    onboarding_context: str = "",
    permission_rules: Optional[list] = None,
) -> Agent:
    """Create a fresh Agent instance (no cache, no shared state).

    Each call returns a new Agent with its own AgentState, eliminating
    the cross-window context pollution issue.
    """
    from agentscope.state import AgentState
    from agentscope.permission import PermissionContext, PermissionMode, PermissionBehavior
    from agentscope.tool import Toolkit
    from agentscope.skill import LocalSkillLoader
    from agentscope.tool._builtin._read import Read
    from agentscope.tool._builtin._write import Write
    from agentscope.tool._builtin._bash import Bash
    from agentscope.tool._builtin._glob import Glob
    from agentscope.tool._builtin._grep import Grep

    BUILTIN_TOOLS = [Read(), Write(), Bash(), Glob(), Grep()]

    full_prompt = system_prompt
    if onboarding_context:
        full_prompt += "\n\n## 项目背景\n\n" + onboarding_context

    tools = list(BUILTIN_TOOLS) + (extra_tools or [])
    loaders = [
        LocalSkillLoader(d, scan_subdir=True)
        for d in (skill_dirs or [])
    ]
    toolkit = Toolkit(tools=tools, skills_or_loaders=loaders)

    state = AgentState()
    if permission_rules:
        state.permission_context = PermissionContext(mode=PermissionMode.ACCEPT_EDITS)
        for rule in permission_rules:
            state.permission_context.deny_rules.setdefault(
                rule.tool_name, []
            ).append(rule) if rule.behavior == PermissionBehavior.DENY else \
            state.permission_context.allow_rules.setdefault(
                rule.tool_name, []
            ).append(rule)

    agent = Agent(
        name=agent_id,
        system_prompt=full_prompt,
        model=get_model(),
        toolkit=toolkit,
        middlewares=middlewares or [],
        state=state,
    )
    log.info("Agent created (fresh): %s", agent_id)
    return agent


# ── Onboarding middleware ──────────────────────────────


class OnboardingMiddleware(MiddlewareBase):
    """Injects project background + task dashboard + memory into system_prompt.

    Static portion: onboarding_context (AGENTS.md content).
    Dynamic portion: formatted dashboard from DASHBOARD.yaml.
    Memory portion: private + shared memory entries.

    Dashboard is filtered by agent_id + window_id, and formatted as
    three sections: 🟢 ready / 🟡 in-progress / ⏳ waiting.
    """

    def __init__(
        self,
        onboarding_context: str = "",
        dashboard_dao=None,          # DashboardDAO | None
        window_id: str = "",
    ):
        self._context = onboarding_context
        self._dashboard_dao = dashboard_dao
        self._window_id = window_id

    async def on_system_prompt(self, agent, prompt: str) -> str:
        additions: list[str] = []

        # Static background
        if self._context:
            additions.append("## 项目背景\n" + self._context)

        # Dynamic dashboard
        if self._dashboard_dao and self._window_id:
            try:
                tasks = self._dashboard_dao.get_tasks_for_agent(
                    agent.name, self._window_id,
                )
                if tasks:
                    additions.append(self._format_dashboard(tasks))
            except Exception:
                pass  # dashboard unavailable → skip quietly

        # Memory injection — read from Markdown files (not SQLite).
        # SQLite is the cloud; MEMORY.md is the local file.
        # Sync is handled by MemorySyncMiddleware (local→cloud)
        # and POST /api/memory/{id}/sync (cloud→local).
        try:
            from ..dao import ConfigDAO
            dao = ConfigDAO(".")
            project_memo = dao.get_project_memo()
            if project_memo.strip():
                # Keep only the first 2000 chars to avoid token bloat
                additions.append("## 项目共识\n" + project_memo[:2000])
        except Exception:
            pass
        except Exception:
            pass  # memory unavailable → skip quietly

        if additions:
            return prompt + "\n\n" + "\n\n".join(additions)
        return prompt

    @staticmethod
    def _format_dashboard(tasks) -> str:
        """Format a list of TaskItem into the three-section agent view."""
        truly_ready = [
            t for t in tasks
            if t.status == "pending" and not t.depends_on
        ]
        in_progress = [t for t in tasks if t.status == "in_progress"]
        blocked = [t for t in tasks if t.status == "blocked"]
        pending_blocked = [
            t for t in tasks
            if t.status == "pending" and t.depends_on
        ]

        lines = ["## 你的任务看板"]

        if truly_ready:
            lines.append("\n🟢 可开始：")
            for t in truly_ready:
                lines.append(f"  · {t.id} {t.title} → 输出到 {t.output or '待定'}")

        if in_progress:
            lines.append("\n🟡 进行中：")
            for t in in_progress:
                lines.append(f"  · {t.id} {t.title}")

        if blocked:
            lines.append("\n🔴 阻塞：")
            for t in blocked:
                reason = t.blocked_reason or "未知原因"
                lines.append(f"  · {t.id} {t.title} — {reason}")

        if pending_blocked:
            lines.append("\n⏳ 等待前置完成：")
            for t in pending_blocked:
                deps = ", ".join(t.depends_on)
                lines.append(f"  · {t.id} {t.title} ← 等待 {deps}")

        return "\n".join(lines)


# ── Memory formatters (module-level) ──────────────


def _format_private_memories(memories) -> str:
    """Format private memory entries for agent self-view."""
    lines = ["## 你的记忆"]
    for m in memories[:15]:
        tag = _memory_tag(m.get("type", ""))
        content = m.get("content", "")
        if len(content) > 150:
            content = content[:147] + "..."
        lines.append(f"  {tag} {content}")
    return "\n".join(lines)


def _format_shared_memories(memories) -> str:
    """Format shared memory entries for team consensus view."""
    lines = ["## 项目共识"]
    for m in memories[:10]:
        tag = _memory_tag(m.get("type", ""))
        content = m.get("content", "")
        if len(content) > 200:
            content = content[:197] + "..."
        lines.append(f"  {tag} {content}")
    return "\n".join(lines)


_MEMORY_TAGS = {
    "fact": "📋", "decision": "🔧", "preference": "⭐",
    "reflection": "💭", "shendu": "🌙", "context": "📝",
}


def _memory_tag(type_name: str) -> str:
    return _MEMORY_TAGS.get(type_name, "•")

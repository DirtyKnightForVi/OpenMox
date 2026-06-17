"""
OpenMox toolkit assembly — per-agent tool/middleware setup.

Two entry points for ChatService:
  - build_openmox_tools_factory()         — extra_agent_tools (async factory)
  - make_middleware_factory()              — extra_agent_middlewares (factory-of-factory)

Also: build_openmox_tools() — legacy FanoutStreamer path (synchronous, deprecated).
"""

from ..dao import ConfigDAO
from ..dao.dashboard_dao import DashboardDAO
from .agent_factory import OnboardingMiddleware
from .dashboard_tools import build_dashboard_tools
from .agent_from_template_tool import AgentFromTemplateTool
from ..memory.capture import MemoryCaptureMiddleware
from ..permission.rules import build_permission_rules
from .logging import get_logger

log = get_logger(__name__)


# ═══════════════════════════════════════════════════════════
# build_openmox_tools — legacy FanoutStreamer path (deprecated)
# ═══════════════════════════════════════════════════════════

def build_openmox_tools(
    *,
    dao: ConfigDAO,
    agent_id: str,
    window_id: str = "",
) -> dict:
    """Assemble tools, middlewares, and permission rules for one agent.

    Used by FanoutStreamer (legacy path). Returns a dict ready to
    unpack into get_agent().
    """
    is_momo = dao.is_momo(agent_id)
    project_root = str(dao.root)
    dashboard_dao = DashboardDAO(project_root)
    momo_id = dao.get_momo_id() or ""

    # ── Tools ─────────────────────────────────
    extra_tools: list = []

    # Dashboard tools (only if dashboard_dao available)
    try:
        extra_tools = build_dashboard_tools(
            storage=None,  # not needed for fanout path
            message_bus=None,
            agent_id=agent_id,
            is_momo=is_momo,
            window_id=window_id,
        )
    except Exception:
        pass

    # AgentFromTemplate (momo only)
    if is_momo:
        try:
            extra_tools.append(AgentFromTemplateTool(
                storage=None, message_bus=None,
                user_id="openmox", session_id=window_id,
                agent_id=agent_id, is_momo=True,
            ))
        except Exception:
            pass

    # Note: CallAgentTool is deprecated. Use TeamSay for agent-to-agent
    # communication (routes through InboxMiddleware + WakeupDispatcher
    # for full middleware chain support).

    # ── Middlewares ───────────────────────────
    onboarding = dao.get_onboarding_context()
    middlewares: list = [
        OnboardingMiddleware(
            onboarding_context=onboarding,
            dashboard_dao=dashboard_dao,
            window_id=window_id,
        ),
        MemoryCaptureMiddleware(
            agent_id=agent_id,
            project_id=project_root,
        ),
    ]

    # CommunicationBudgetMiddleware
    from .communication_budget_middleware import CommunicationBudgetMiddleware
    middlewares.append(
        CommunicationBudgetMiddleware(
            dashboard_dao=dashboard_dao,
            agent_id=agent_id,
            window_id=window_id,
            momo_id=momo_id,
        ),
    )

    # ── Permission rules ─────────────────────
    all_ids = [a.id for a in dao.list_agents()]
    perm_rules = build_permission_rules(agent_id, all_ids, is_momo=is_momo)

    return {
        "extra_tools": extra_tools,
        "middlewares": middlewares,
        "permission_rules": perm_rules,
    }


# ═══════════════════════════════════════════════════════════
# ChatService extra_factories (async) — PRIMARY PATH
# ═══════════════════════════════════════════════════════════


async def _resolve_project_path(session_id: str) -> str:
    """Derive project_path from the ws_registry, fall back to current dir.

    ChatService passes ``session_id`` as ``{window_id}:{agent_id}``,
    but the registry stores entries under the bare ``window_id``.
    """
    from .ws_registry import get_project_path
    project_path = await get_project_path(session_id)
    if project_path:
        return project_path
    # Strip trailing ``:agent_id`` suffix and retry
    if ":" in session_id:
        window_id = session_id.rsplit(":", 1)[0]
        project_path = await get_project_path(window_id)
        if project_path:
            return project_path
    return "."


def make_tools_factory(
    *,
    storage,
    message_bus,
):
    """Return an async factory for ChatService.extra_agent_tools.

    The returned factory captures ``storage`` and ``message_bus`` via
    closure so ChatService's factory signature ``(user_id, agent_id,
    session_id)`` can pass them through to tool constructors.

    Usage in main.py lifespan::

        tools_factory = make_tools_factory(storage=storage, message_bus=message_bus)
        chat_service = ChatService(..., extra_agent_tools=tools_factory)
    """

    async def _factory(user_id: str, agent_id: str, session_id: str) -> list:
        project_path = await _resolve_project_path(session_id)
        dao = ConfigDAO(project_path)
        is_momo = dao.is_momo(agent_id)
        project_root = str(dao.root)

        tools: list = []

        # Dashboard tools
        try:
            tools.extend(build_dashboard_tools(
                storage=storage, message_bus=message_bus,
                agent_id=agent_id, is_momo=is_momo, window_id=session_id,
            ))
        except Exception:
            pass

        # AgentFromTemplate (momo only)
        if is_momo:
            try:
                tools.append(AgentFromTemplateTool(
                    storage=storage, message_bus=message_bus,
                    user_id=user_id, session_id=session_id,
                    agent_id=agent_id, is_momo=True,
                ))
            except Exception:
                pass

        log.info(
            "extra_tools factory: agent=%s session=%s project=%s tools=%d momo=%s",
            agent_id, session_id[:20], project_root, len(tools), is_momo,
        )
        return tools

    return _factory


# Legacy alias — kept for backward ref compatibility in chat.py comments
build_openmox_tools_factory = None  # replaced by make_tools_factory()


def make_middleware_factory(
    *,
    message_bus,
    project_root: str = ".",
):
    """Return an async factory for ChatService.extra_agent_middlewares.

    The returned factory captures ``message_bus`` and ``project_root``
    so ContextSeedingMiddleware and WindowPublishMiddleware can receive
    the bus at construction time — ChatService's factory signature
    passes only (user_id, agent_id, session_id).

    Usage in main.py lifespan::

        middleware_factory = make_middleware_factory(
            message_bus=message_bus, project_root=".",
        )
        chat_service = ChatService(
            ...,
            extra_agent_middlewares=middleware_factory,
        )

    Middleware order (onion model, appended AFTER framework's built-in chain):
      1. ContextSeedingMiddleware — read window stream → seed context
      2. OnboardingMiddleware — inject system_prompt + dashboard + memory
      3. MemoryCaptureMiddleware — extract memories on context compression
      4. CommunicationBudgetMiddleware — enforce peer-to-peer budget
      5. WindowPublishMiddleware — publish public events → window stream
    """

    from .context_seeding_middleware import ContextSeedingMiddleware
    from .window_publish_middleware import WindowPublishMiddleware
    from .communication_budget_middleware import CommunicationBudgetMiddleware
    from .memory_sync_middleware import MemorySyncMiddleware

    async def _factory(user_id: str, agent_id: str, session_id: str) -> list:
        project_path = await _resolve_project_path(session_id)
        dao = ConfigDAO(project_path)
        is_momo = dao.is_momo(agent_id)
        proj_root = str(dao.root)
        momo_id = dao.get_momo_id() or ""
        dashboard_dao = DashboardDAO(proj_root)
        onboarding = dao.get_onboarding_context()

        window_id = session_id

        middlewares = [
            ContextSeedingMiddleware(
                message_bus=message_bus,
                window_id=window_id,
                agent_id=agent_id,
                is_momo=is_momo,
            ),
            OnboardingMiddleware(
                onboarding_context=onboarding,
                dashboard_dao=dashboard_dao,
                window_id=window_id,
            ),
            MemoryCaptureMiddleware(
                agent_id=agent_id,
                project_id=proj_root,
            ),
            CommunicationBudgetMiddleware(
                dashboard_dao=dashboard_dao,
                agent_id=agent_id,
                window_id=window_id,
                momo_id=momo_id,
            ),
            MemorySyncMiddleware(
                agent_id=agent_id,
                project_root=proj_root,
            ),
            WindowPublishMiddleware(
                message_bus=message_bus,
                window_id=window_id,
                agent_id=agent_id,
            ),
        ]

        log.info(
            "middleware factory: agent=%s session=%s momo=%s count=%d",
            agent_id, session_id[:20], is_momo, len(middlewares),
        )
        return middlewares

    return _factory

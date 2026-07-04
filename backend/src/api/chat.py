"""
WebSocket chat handler — receives messages, routes @mentions, streams via ChatService.

The /ws endpoint is the core transport layer. It speaks PilotDeck V2 protocol.

Architecture (revised):
  1. Human sends pilotdeck-command via WebSocket
  2. MentionRouter parses @agent mentions
  3. Human message published to window stream (shared timeline)
  4. Persisted to SQLite messages table (audit)
  5. For each mentioned agent: spawn ChatService.run() as background task
  6. Window stream events → ws.send_json() (all public events)
  7. Chain trigger: agent reply text containing @mentions → recurse
"""

import json
import time
import re
import os
import asyncio
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect

from ..orchestration.router import MentionRouter
from ..core.store import append_message
from ..core.logging import get_logger, LogContext
from ..core.ws_registry import register as ws_register, unregister as ws_unregister
from .projects import _init_momo_if_needed

log = get_logger(__name__)

# ── Session key parsing ────────────────────────────────

_AGENT_RE = re.compile(r":agent=([a-z0-9_-]+)$", re.IGNORECASE)


def _parse_agent_from_session(session_key: str) -> str | None:
    """Extract agent_id from sessionKey like 'web:s_xxx:agent=product-manager'."""
    m = _AGENT_RE.search(session_key)
    return m.group(1) if m else None


# ── Chain-trigger depth limit ───────────────────────

_MAX_CHAIN_DEPTH = 5


# ── Helper: window stream key ──────────────────────

def _window_key(window_id: str) -> str:
    return f"window:{window_id}:events"


# ── WebSocket handler ──────────────────────────────────


async def handle_ws(ws: WebSocket) -> None:
    """Main WebSocket event loop — called from main.py's /ws endpoint."""
    tid = LogContext.set_trace_id()
    await ws.accept()
    log.info("WebSocket connected")

    # PilotDeck V2 handshake
    await _safe_send(ws, {
        "type": "config:reloaded",
        "changedPaths": [],
        "changeClasses": [],
    })
    await _safe_send(ws, {
        "type": "server_info",
        "mode": "in_process",
    })

    mention_router = MentionRouter()
    _registered_window: str | None = None
    _project_path: str = "."
    _window_sub_task: asyncio.Task | None = None

    async def _subscribe_window_stream(window_id: str):
        """Persistently forward window stream events to the WebSocket.

        Skips ``human_message`` — those are sent directly in
        _handle_command to avoid the Pub/Sub subscription race.
        """
        from main import app as _app
        _bus = getattr(_app.state, "message_bus", None)
        if _bus is None:
            return
        key = _window_key(window_id)
        try:
            async for payload in _bus.subscribe(key):
                if payload.get("type") == "human_message":
                    continue  # already sent directly
                await _safe_send(ws, payload)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.debug("Window stream subscription ended for %s", window_id[:20])

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type", "")

            if msg_type == "check-session-status":
                await _safe_send(ws, {
                    "type": "session-status",
                    "status": "idle",
                })

            elif msg_type == "pilotdeck-command":
                options: dict = msg.get("options", {})
                window_id: str = (
                    options.get("sessionId", "")
                    or options.get("sessionKey", "")
                )
                _project_path = options.get(
                    "projectPath", options.get("cwd", "."),
                )

                if _registered_window is None:
                    _registered_window = window_id
                    # Resolve project_path: if the frontend sent "." (default),
                    # look up the real path from the SQLite projects table by
                    # matching against the mentioned agents.
                    if _project_path == ".":
                        from ..dao import ConfigDAO
                        mentioned_test, _ = mention_router.parse(
                            msg.get("command", ""),
                        )
                        _project_path = _resolve_project_from_agents(
                            mentioned_test,
                        )
                    await ws_register(window_id, ws, _project_path)
                    log.info(
                        "WS registered: window=%s project=%s",
                        window_id[:30], _project_path,
                    )
                    # Start persistent window stream subscription.
                    # This delivers human_message, agent_report (from
                    # report_to_group tool), and task_progress events.
                    _window_sub_task = asyncio.create_task(
                        _subscribe_window_stream(window_id),
                    )

                await _handle_command(
                    ws, msg, mention_router, window_id, _project_path,
                    # _invoked_agents starts empty — only chain-triggers
                    # populate it to prevent re-invocation loops.
                )

    except WebSocketDisconnect:
        log.info("WebSocket disconnected")
    except RuntimeError as e:
        # "WebSocket is not connected. Need to call "accept" first." is raised
        # by Starlette when the client disconnects before the first receive.
        # This is normal during React StrictMode double-mount or page hot-reload.
        msg = str(e)
        if "accept" in msg and "not connected" in msg.lower():
            log.info("WebSocket client disconnected before handshake complete")
        else:
            log.error("WebSocket error: %s", e)
    except Exception as e:
        log.error("WebSocket error: %s", e)
    finally:
        if _window_sub_task is not None:
            _window_sub_task.cancel()
            try:
                await _window_sub_task
            except (asyncio.CancelledError, Exception):
                pass
        if _registered_window is not None:
            await ws_unregister(_registered_window)
            log.info("WS unregistered: window=%s", _registered_window[:30])


# ── Chain-trigger depth limit ───────────────────────

_MAX_CHAIN_DEPTH = 5


def _resolve_project_from_agents(agent_ids: list[str]) -> str:
    """Find the project path that contains the mentioned agents.

    Scans all projects in the SQLite database.  Returns the first
    project that has at least one of the mentioned agents, or "."
    if none found.
    """
    if not agent_ids:
        log.info("_resolve_project: no agent ids to resolve, returning '.'")
        return "."
    import sqlite3
    from ..dao import ConfigDAO
    try:
        db = sqlite3.connect("data/openmox.db")
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT name, full_path FROM projects ORDER BY created_at DESC",
        ).fetchall()
        db.close()
        log.info(
            "_resolve_project: scanning %d projects for agents=%s",
            len(rows), agent_ids,
        )
        for row in rows:
            proj_path = row["full_path"]
            dao = ConfigDAO(proj_path)
            existing = {a.id for a in dao.list_agents()}
            log.info(
                "_resolve_project: project=%s agents=%s",
                proj_path[-30:], sorted(existing),
            )
            if existing & set(agent_ids):
                log.info(
                    "_resolve_project: MATCH project=%s for agents=%s",
                    proj_path, agent_ids,
                )
                return proj_path
        log.warning(
            "_resolve_project: no project matched agents=%s",
            agent_ids,
        )
    except Exception as e:
        log.warning("_resolve_project: error scanning projects: %s", e)
    return "."


# ── Command handler ────────────────────────────────────


async def _handle_command(
    ws: WebSocket,
    msg: dict,
    mention_router: MentionRouter,
    window_id: str,
    project_path: str,
    _chain_depth: int = 0,
    _invoked_agents: frozenset = frozenset(),
) -> None:
    """Process a pilotdeck-command: parse @agent, spawn ChatService tasks,
    subscribe to window stream for events.

    Args:
        _chain_depth: Recursion depth for chain-triggered @mentions.
        _invoked_agents: Agent IDs already invoked in this command tree.
            Chain-triggers skip agents already in this set to prevent
            feedback loops when multiple agents are @mentioned together.
    """
    command: str = msg.get("command", "")

    # Parse @mentions
    mentioned, clean_msg = mention_router.parse(command)

    # Deduplicate against already-invoked agents (chain-trigger guard)
    if _invoked_agents:
        mentioned = [a for a in mentioned if a not in _invoked_agents]
        if not mentioned:
            log.info("Chain trigger depth=%d: all agents already invoked, skipping", _chain_depth)
            return

    log.info(
        "cmd depth=%d session=%s @agents=%s msg=%.60s",
        _chain_depth,
        window_id[:30],
        mentioned or ["-"],
        clean_msg,
    )

    # ── Get app-level dependencies (stored in lifespan) ──
    from main import app as _app
    storage = getattr(_app.state, 'storage', None)
    chat_service = getattr(_app.state, 'chat_service', None)
    chat_run_registry = getattr(_app.state, 'chat_run_registry', None)
    message_bus = getattr(_app.state, 'message_bus', None)

    if not all([storage, chat_service, chat_run_registry, message_bus]):
        log.error("App state incomplete — missing storage/chat_service/chat_run_registry/message_bus")
        await _safe_send(ws, {
            "type": "system_message",
            "content": "服务尚未就绪，请稍后再试。",
        })
        return

    # Scope Redis keys by project path so each project gets
    # isolated namespace (agents, sessions, teams, messages).
    import hashlib
    _project_hash = hashlib.md5(project_path.encode()).hexdigest()[:8]
    user_id = f"openmox:{_project_hash}"

    # ── Ensure project Team for TeamSay communication ──
    # Reads/creates .Project/team.yaml, registers agents,
    # creates window-scoped sessions, binds them to the Team.
    team_id = await _ensure_project_team(
        storage=storage,
        user_id=user_id,
        window_id=window_id,
        project_path=project_path,
    )
    if team_id:
        log.info("Team set up: team_id=%s user_id=%s window=%s",
                 team_id[:12], user_id, window_id[:20])
    else:
        log.warning("Team NOT set up for user_id=%s window=%s",
                     user_id, window_id[:20])

    # ── Default routing to momo ────────────────────
    if not mentioned:
        from ..dao import ConfigDAO
        dao = ConfigDAO(project_path)
        momo_id = dao.get_momo_id()
        if momo_id:
            mentioned = [momo_id]
            log.info("No @mention → defaulting to momo (%s)", momo_id)
            # Register the project-scoped agent into Redis so ChatService
            # (which uses the singleton storage) can find it later.
            try:
                ok = await storage.ensure_agent_from_path(
                    user_id, momo_id, project_path,
                )
                if not ok:
                    log.warning(
                        "momo %r resolved from .Project/momo.yaml but "
                        "not found in .Agents/ — agent not created yet?",
                        momo_id,
                    )
            except Exception as exc:
                log.warning(
                    "Failed to register momo %r from %s: %s",
                    momo_id, project_path, exc,
                )
        else:
            log.warning("No @mention and no momo configured — message dropped")
            await append_message(
                window_id, content=command,
                speaker_type="human", speaker_id="user",
            )
            await _safe_send(ws, {
                "type": "system_message",
                "content": "没有指定 Agent，且项目未配置 momo。请 @ 你想对话的同事。",
            })
            return

    # ── Publish human message to window stream ─────
    if _chain_depth == 0:
        human_event = {
            "type": "human_message",
            "content": command,
            "speaker_id": "user",
            "_timestamp": time.time(),
        }
        try:
            key = _window_key(window_id)
            await message_bus.log_append(key, human_event, max_len=2000)
            await message_bus.publish(key, human_event)
        except Exception:
            pass  # best-effort
        # Push directly for immediate UI feedback (window stream
        # subscription may not be ready yet — Pub/Sub race).
        await _safe_send(ws, human_event)

        # Persist to SQLite messages (audit)
        await append_message(
            window_id, content=command,
            speaker_type="human", speaker_id="user",
        )

    # ── Ensure project has a momo agent (auto-init for legacy projects) ──
    _init_momo_if_needed(project_path)

    # ── Spawn ChatService.run() for each mentioned agent ──
    results: list[dict] = []
    log.info("_handle_command: spawning %d agents: %s", len(mentioned), mentioned)

    async def _run_one(agent_id: str) -> dict:
        """Run one agent via ChatService and collect result text."""
        session_id = f"{window_id}:{agent_id}"

        # Register the project-scoped agent into Redis so the singleton
        # storage can find it — otherwise ChatService._run_impl gets 404.
        try:
            ok = await storage.ensure_agent_from_path(
                user_id, agent_id, project_path,
            )
            if not ok:
                log.warning(
                    "Agent %r not found in project %s/.Agents/ — "
                    "chat may fail",
                    agent_id, project_path,
                )
                # Send immediate user feedback instead of hanging for 10 s.
                await _safe_send(ws, {
                    "type": "system_message",
                    "content": (
                        f"Agent「{agent_id}」在此项目中尚未创建。"
                        f"请先在项目设置中创建该 Agent。"
                    ),
                })
                return {"agent_id": agent_id, "text": ""}
        except Exception as exc:
            log.warning(
                "Failed to register agent %r from %s: %s",
                agent_id, project_path, exc,
            )

        # Ensure session exists
        from agentscope.app.storage import SessionConfig, SessionSource
        from agentscope.state import AgentState

        # Build model config from settings
        from ..core.settings import get_settings
        s = get_settings()
        from agentscope.app.storage import ChatModelConfig
        model_cfg = ChatModelConfig(
            type="deepseek_chat",
            credential_id="default",
            model=s.deepseek_model,
            parameters={"thinking_enable": os.environ.get("OPENMOX_THINKING", "").lower() in ("1", "true", "yes")},
        )

        # Reset the agent state for a fresh user-initiated run.
        # AgentScope persists the previous run's state (including
        # pending tool calls in context), and if the previous run
        # left tool calls in stale states, _check_incoming_event
        # rejects new messages with "Agent is waiting for N tool
        # calls and received no event."
        #
        # Context is cleared here and rebuilt by
        # ContextSeedingMiddleware from the window stream.
        try:
            old_session = await storage.get_session(
                user_id, agent_id, session_id,
            )
            if old_session and old_session.state:
                old_session.state.context = []
                old_session.state.reply_id = ""
                old_session.state.cur_iter = 0
                await storage.update_session_state(
                    user_id, agent_id, session_id, old_session.state,
                )
        except Exception:
            pass

        await storage.upsert_session(
            user_id, agent_id,
            config=SessionConfig(
                # Use project_path as workspace_id so
                # OpenMoxWorkspaceManager scopes the workdir correctly.
                workspace_id=project_path,
                chat_model_config=model_cfg,
            ),
            session_id=session_id,
            source=SessionSource.USER,
        )

        # Build input message
        from agentscope.message import Msg
        try:
            input_msg = Msg(
                name="user",
                content=[{"type": "text", "text": clean_msg}],
                role="user",
            )
        except Exception:
            input_msg = Msg(
                name="user",
                content=clean_msg,
                role="user",
            )

        # ── Run agent via ChatService ──
        # Agent events (THINKING, TOOL_CALL, TOOL_RESULT, TEXT)
        # are streamed via the SSE endpoint /api/sessions/{sid}/stream
        # — no collector, no sub_ready, no drain window needed here.
        # The frontend connects to SSE directly per agent.
        #
        # Group-chat messages come from the agent's report_to_group tool,
        # which publishes to the window stream as complete Markdown.
        # Chain-trigger (@mentions) are detected from window stream
        # messages, not from session events.

        # ── Push agent:busy to WebSocket ─────────
        # Includes session_id so the frontend can open an SSE
        # connection for this agent's task-panel events.
        await _safe_send(ws, {
            "type": "agent:busy",
            "_agent_id": agent_id,
            "session_id": session_id,
            "_timestamp": time.time(),
        })

        _t0 = time.time()
        log.info("_run_one: entering chat_service.run() session=%s", session_id[:30])
        _chat_error = None
        try:
            await asyncio.wait_for(
                chat_service.run(
                    user_id=user_id,
                    session_id=session_id,
                    agent_id=agent_id,
                    input_msg=input_msg,
                ),
                timeout=120.0,
            )
        except asyncio.TimeoutError:
            log.error("_run_one: chat_service.run() timed out after 120s for %s", session_id[:30])
            _chat_error = "timeout"
        except Exception as e:
            log.error("_run_one: chat_service.run() failed for %s: %s", session_id[:30], e)
            _chat_error = str(e)
        _elapsed = time.time() - _t0
        log.info("_run_one: chat_service.run() returned after %.1fs session=%s error=%s",
                 _elapsed, session_id[:30], _chat_error or "none")

        # ── Push agent:idle to WebSocket ──────────
        await _safe_send(ws, {
            "type": "agent:idle",
            "_agent_id": agent_id,
            "_timestamp": time.time(),
        })

        # ── Clear stale agent context unconditionally ──
        # AgentScope's WakeupDispatcher skips sessions with parked
        # tool calls.  Clear the context after every run so the next
        # run (user-initiated or TeamSay wake-up) starts fresh.
        try:
            sess = await storage.get_session(user_id, agent_id, session_id)
            if sess and sess.state:
                sess.state.context = []
                sess.state.reply_id = ""
                sess.state.cur_iter = 0
                await storage.update_session_state(
                    user_id, agent_id, session_id, sess.state,
                )
        except Exception:
            pass

        # If chat_service crashed, tell the user.
        if _chat_error:
            await _safe_send(ws, {
                "type": "system_message",
                "content": (
                    f"Agent「{agent_id}」执行异常"
                    + (f"（{_chat_error}）" if _chat_error != "timeout" else "（超时）")
                    + "，请重试。"
                ),
            })

        # ── Read reply text from storage ──────────
        # After chat_service.run(), the reply message is persisted
        # by ChatService._run_impl.  Read it back for chain triggering
        # and SQLite persistence.
        full_text = ""
        try:
            reply_msg = await storage.get_message(
                user_id, session_id, agent_id,
            )
            if reply_msg:
                text_blocks = [
                    b.text for b in reply_msg.content
                    if hasattr(b, "text") and b.text
                ]
                full_text = "\n".join(text_blocks)
        except Exception:
            pass

        return {"agent_id": agent_id, "text": full_text}

    # Run all agents concurrently
    results = await asyncio.gather(
        *[_run_one(aid) for aid in mentioned],
        return_exceptions=True,
    )

    # ── Persist + chain-trigger ─────────────────────
    # Collect all text to scan for @mentions (agent text + report_to_group)
    for agent_id, result in zip(mentioned, results):
        if isinstance(result, Exception):
            log.error("Agent %s failed: %s", agent_id, result)
            continue

        r = result if isinstance(result, dict) else {"agent_id": agent_id, "text": ""}

        # Scan both the agent's reply text AND recent agent_report events
        # from the window stream for @mentions.
        texts_to_scan = [r["text"]] if r["text"] else []

        # Also check window stream for agent_report events from this agent
        try:
            for _eid, evt in await message_bus.log_read(
                _window_key(window_id), max_count=50,
            ):
                if evt.get("type") == "agent_report" and evt.get("_agent_id") == agent_id:
                    texts_to_scan.append(evt.get("content", ""))
        except Exception:
            pass

        if not texts_to_scan:
            continue

        # Chain trigger: scan all texts for @mentions
        if _chain_depth < _MAX_CHAIN_DEPTH:
            reply_mentioned = set()
            for text in texts_to_scan:
                m, _ = mention_router.parse(text)
                reply_mentioned.update(m)
            reply_mentioned = list(reply_mentioned)
            # Build the set of already-invoked agents for the next depth:
            # original invoked + agents just spawned in this batch.
            next_invoked = _invoked_agents | frozenset(mentioned)
            # Skip chain-trigger for agents already in invoked set
            reply_mentioned = [
                a for a in reply_mentioned
                if a not in next_invoked
            ]
            if reply_mentioned:
                log.info(
                    "Chain trigger depth=%d: @%s ← %s",
                    _chain_depth + 1, reply_mentioned, r["agent_id"],
                )
                chain_msg = {
                    "type": "pilotdeck-command",
                    "command": r["text"],
                    "options": {
                        "sessionKey": window_id,
                        "sessionId": window_id,
                        "projectPath": project_path,
                        "cwd": project_path,
                    },
                }
                await _handle_command(
                    ws, chain_msg, mention_router,
                    window_id, project_path, _chain_depth + 1,
                    _invoked_agents=next_invoked,
                )


# ── TaskContext seeding ──────────────────────────────


async def _seed_task_context(
    *,
    storage,
    user_id: str,
    agent_id: str,
    session_id: str,
    project_path: str,
    window_id: str,
    clean_msg: str,
) -> int:
    """Inject a plan-execute TaskContext into the agent's session state.

    Reads tasks from DASHBOARD.yaml assigned to this agent, wraps them
    with a head task (claim + report_to_group) and a tail task
    (completion report_to_group), and writes them into the agent's
    ``AgentState.tasks_context`` in Redis.

    Returns the number of tasks seeded (0 = nothing to do).
    """
    from ..dao.dashboard_dao import DashboardDAO
    from agentscope.state import Task, TaskContext

    dd = DashboardDAO(project_path)
    dash_tasks = dd.get_tasks_for_agent(agent_id, window_id)

    # Only seed if there are tasks assigned to this agent
    if not dash_tasks:
        return 0

    tasks: list[Task] = []

    # ── Head: claim + immediate feedback ──
    pending_titles = ", ".join(
        t.title for t in dash_tasks if t.status == "pending"
    )
    head_desc = (
        f"📢 向群聊汇报：调用 report_to_group 告知你已经认领了以下任务并开始工作："
        f"{pending_titles or '任务'}。"
        f"同时调用 update_dashboard 将任务状态更新为 in_progress。"
    )
    tasks.append(Task(
        subject="📢 认领并汇报任务",
        description=head_desc,
        state="pending",
        metadata={"type": "report", "action": "claim"},
    ))

    # ── Middle: DASHBOARD tasks ──
    for dt in dash_tasks:
        tasks.append(Task(
            subject=dt.title,
            description=dt.description or f"执行任务: {dt.title}",
            state="pending" if dt.status != "done" else "completed",
            metadata={"dashboard_id": dt.id},
        ))

    # ── Tail: completion report ──
    tail_desc = (
        "📢 所有任务完成后，调用 report_to_group 向群聊发送完整的成果汇报。"
        "然后调用 update_dashboard 将已完成的任务标记为 done。"
    )
    tasks.append(Task(
        subject="📢 完成汇报",
        description=tail_desc,
        state="pending",
        metadata={"type": "report", "action": "complete"},
    ))

    task_context = TaskContext(tasks=tasks)

    # Write into session state
    try:
        sess = await storage.get_session(user_id, agent_id, session_id)
        if sess and sess.state:
            sess.state.tasks_context = task_context
            await storage.update_session_state(
                user_id, agent_id, session_id, sess.state,
            )
        log.info(
            "_seed_task_context: agent=%s tasks=%d (head+%d+tail)",
            agent_id, len(tasks), len(dash_tasks),
        )
    except Exception as e:
        log.warning("_seed_task_context failed: %s", e)

    return len(tasks)


# ── Team management ─────────────────────────────────

# Track Windows that already have sessions bound to their project Team.
_bound_windows: set[str] = set()


async def _ensure_project_team(
    *,
    storage,
    user_id: str,
    window_id: str,
    project_path: str,
) -> str | None:
    """Ensure this project has an AgentScope Team for TeamSay communication.

    1. Read .Project/team.yaml.  If missing, auto-create from .Agents/ agents.
    2. Create the corresponding AgentScope Team in Redis (if not exists).
    3. Bind every agent's window-scoped session to the Team.
    4. Return the team_id, or None if the project has fewer than 2 agents.

    Idempotent — subsequent calls for the same window are no-ops.
    """
    if window_id in _bound_windows:
        # Return the already-bound team_id from the first session.
        momo_id = _get_momo_for_project(project_path)
        if momo_id:
            sess = await storage.get_session(
                user_id, momo_id, f"{window_id}:{momo_id}",
            )
            if sess and sess.team_id:
                return sess.team_id
        return None

    from ..dao import ConfigDAO
    from agentscope.app.storage import (
        TeamRecord, TeamData, SessionConfig, SessionSource,
        ChatModelConfig,
    )
    from ..core.settings import get_settings

    dao = ConfigDAO(project_path)
    agents = dao.list_agents()
    if len(agents) < 2:
        log.info("Team: project %s has <2 agents, skipping",
                 project_path[-30:])
        return None

    momo_id = dao.get_momo_id()
    if not momo_id:
        log.warning("Team: no momo configured for %s", project_path[-30:])
        return None

    # ── Read or create team.yaml ──────────────────
    team_cfg = dao.read_team_yaml()
    if team_cfg is None:
        # Auto-create: all agents as members, momo as leader.
        member_ids = [a.id for a in agents]
        dao.write_team_yaml(momo_id, member_ids)
        log.info("Team: auto-created team.yaml — leader=%s members=%s",
                 momo_id, member_ids)
        team_cfg = {"leader": momo_id, "members": member_ids}

    leader_id = team_cfg.get("leader", momo_id)
    member_ids: list[str] = list(team_cfg.get("members", []))

    log.info("Team: window=%s leader=%s members=%s",
             window_id[:30], leader_id, member_ids)

    # ── Register agents + create sessions ─────────
    s = get_settings()
    model_cfg = ChatModelConfig(
        type="deepseek_chat",
        credential_id="default",
        model=s.deepseek_model,
        parameters={},
    )

    all_ids = list(dict.fromkeys([leader_id] + member_ids))
    for aid in all_ids:
        await storage.ensure_agent_from_path(user_id, aid, project_path)
        session_id = f"{window_id}:{aid}"
        await storage.upsert_session(
            user_id, aid,
            config=SessionConfig(
                workspace_id=project_path,
                chat_model_config=model_cfg,
            ),
            session_id=session_id,
            source=SessionSource.USER,
        )

    # ── Create/update Team in Redis ───────────────
    # Use leader's session as the Team's anchor session.
    leader_session = f"{window_id}:{leader_id}"
    team = TeamRecord(
        user_id=user_id,
        session_id=leader_session,
        data=TeamData(
            name=f"OpenMox ({project_path.split('/')[-1]})",
            description="Multi-agent collaborative project",
            member_ids=[],
        ),
    )
    await storage.upsert_team(user_id, team)

    for aid in all_ids:
        session_id = f"{window_id}:{aid}"
        await storage.set_session_team_id(user_id, session_id, team.id)
        team.data.member_ids.append(aid)

    await storage.upsert_team(user_id, team)
    _bound_windows.add(window_id)

    log.info("Team: ready — team=%s sessions=%d",
             team.id[:12], len(all_ids))
    return team.id


def _get_momo_for_project(project_path: str) -> str | None:
    """Quick lookup: return the momo agent_id for a project."""
    from ..dao import ConfigDAO
    dao = ConfigDAO(project_path)
    return dao.get_momo_id()


# ── Helpers ────────────────────────────────────────────


async def _safe_send(ws: WebSocket, data: dict) -> None:
    """Send JSON over WebSocket, silently ignoring disconnect errors."""
    try:
        await ws.send_text(json.dumps(data, ensure_ascii=False))
    except Exception:
        pass

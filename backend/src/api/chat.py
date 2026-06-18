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
        return "."
    import sqlite3
    try:
        db = sqlite3.connect("data/openmox.db")
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT name, full_path FROM projects ORDER BY created_at DESC",
        ).fetchall()
        db.close()
        for row in rows:
            proj_path = row["full_path"]
            dao = ConfigDAO(proj_path)
            existing = {a.id for a in dao.list_agents()}
            if existing & set(agent_ids):
                return proj_path
    except Exception:
        pass
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
    await _ensure_project_team(
        storage=storage,
        user_id=user_id,
        window_id=window_id,
        project_path=project_path,
    )

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
        # Also push directly to WebSocket for immediate UI feedback
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

        # ── Run agent via ChatService, collect events → WS ──
        sub_ready = asyncio.Event()
        text_parts: list[str] = []

        # Extract agent_id from session_id for event tagging.
        # Session format: "{window_id}:{agent_id}"
        _current_agent = session_id.rsplit(":", 1)[-1] if ":" in session_id else ""

        async def _collect():
            event_count = 0
            async for payload in message_bus.session_subscribe_events(
                session_id, on_ready=sub_ready.set,
            ):
                event_count += 1
                etype = payload.get("type", "?")
                # Inject _agent_id so frontend / tests can group events by agent
                if _current_agent and "_agent_id" not in payload:
                    payload["_agent_id"] = _current_agent
                # Forward every event to WebSocket directly
                await _safe_send(ws, payload)
                if etype == "TEXT_BLOCK_DELTA":
                    text_parts.append(payload.get("delta", ""))
                elif etype == "REPLY_END":
                    log.info(
                        "_collect: agent=%s REPLY_END after %d events, text_len=%d",
                        _current_agent, event_count, len("".join(text_parts)),
                    )
                    return
            log.warning(
                "_collect: agent=%s stream ended without REPLY_END, events=%d",
                _current_agent, event_count,
            )

        collector_task = asyncio.create_task(_collect())
        await asyncio.wait_for(sub_ready.wait(), timeout=5.0)
        await asyncio.sleep(0)  # let collector enter async-for

        # ── Push agent:busy to WebSocket ─────────
        await _safe_send(ws, {
            "type": "agent:busy",
            "_agent_id": agent_id,
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

        # Don't wait for collector — cancel it.  AgentScope's stream may
        # end without REPLY_END when the ReAct loop pauses for external
        # input, hits max_iters, or a tool raises.  Instead of hanging
        # the frontend on three dots, we push agent:idle immediately.
        collector_task.cancel()
        try:
            await collector_task
        except asyncio.CancelledError:
            pass

        # ── Push agent:idle to WebSocket ──────────
        await _safe_send(ws, {
            "type": "agent:idle",
            "_agent_id": agent_id,
            "_timestamp": time.time(),
        })

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

        full_text = "".join(text_parts)

        # ── Guard: if agent produced no visible text, push a fallback ──
        if not full_text.strip():
            await _safe_send(ws, {
                "type": "system_message",
                "content": (
                    f"Agent「{agent_id}」已完成执行但未生成文本回复。"
                    f"可能是工具调用后未进行总结。请重试或检查 Agent 的 system prompt。"
                ),
            })

        return {"agent_id": agent_id, "text": full_text}

    # Run all agents concurrently
    results = await asyncio.gather(
        *[_run_one(aid) for aid in mentioned],
        return_exceptions=True,
    )

    # ── Persist + chain-trigger ─────────────────────
    for agent_id, result in zip(mentioned, results):
        if isinstance(result, Exception):
            log.error("Agent %s failed: %s", agent_id, result)
            continue

        r = result if isinstance(result, dict) else {"agent_id": agent_id, "text": ""}
        if not r["text"]:
            continue

        await append_message(
            window_id, content=r["text"],
            speaker_type="agent", speaker_id=r["agent_id"],
        )

        # Check if agent's reply contains @mentions → chain trigger
        if _chain_depth < _MAX_CHAIN_DEPTH:
            reply_mentioned, _ = mention_router.parse(r["text"])
            if reply_mentioned:
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

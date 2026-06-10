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
                    await ws_register(window_id, ws, _project_path)
                    log.info(
                        "WS registered: window=%s project=%s",
                        window_id[:30], _project_path,
                    )

                await _handle_command(ws, msg, mention_router, window_id, _project_path)

    except WebSocketDisconnect:
        log.info("WebSocket disconnected")
    except Exception as e:
        log.error("WebSocket error: %s", e)
    finally:
        if _registered_window is not None:
            await ws_unregister(_registered_window)
            log.info("WS unregistered: window=%s", _registered_window[:30])


# ── Chain-trigger depth limit ───────────────────────

_MAX_CHAIN_DEPTH = 5
# ── Command handler ────────────────────────────────────


async def _handle_command(
    ws: WebSocket,
    msg: dict,
    mention_router: MentionRouter,
    window_id: str,
    project_path: str,
    _chain_depth: int = 0,
) -> None:
    """Process a pilotdeck-command: parse @agent, spawn ChatService tasks,
    subscribe to window stream for events.
    """
    command: str = msg.get("command", "")

    # Parse @mentions
    mentioned, clean_msg = mention_router.parse(command)

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

    # ── Default routing to momo ────────────────────
    if not mentioned:
        from ..dao import ConfigDAO
        dao = ConfigDAO(project_path)
        momo_id = dao.get_momo_id()
        if momo_id:
            mentioned = [momo_id]
            log.info("No @mention → defaulting to momo (%s)", momo_id)
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

    # ── Spawn ChatService.run() for each mentioned agent ──
    user_id = "openmox"
    results: list[dict] = []
    log.info("_handle_command: spawning %d agents: %s", len(mentioned), mentioned)

    async def _run_one(agent_id: str) -> dict:
        """Run one agent via ChatService and collect result text."""
        session_id = f"{window_id}:{agent_id}"

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
                workspace_id="default",
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

        async def _collect():
            async for payload in message_bus.session_subscribe_events(
                session_id, on_ready=sub_ready.set,
            ):
                # Forward every event to WebSocket directly
                await _safe_send(ws, payload)
                if payload.get("type") == "TEXT_BLOCK_DELTA":
                    text_parts.append(payload.get("delta", ""))
                elif payload.get("type") == "REPLY_END":
                    break

        collector_task = asyncio.create_task(_collect())
        await asyncio.wait_for(sub_ready.wait(), timeout=5.0)
        await asyncio.sleep(0)  # let collector enter async-for

        await chat_service.run(
            user_id=user_id,
            session_id=session_id,
            agent_id=agent_id,
            input_msg=input_msg,
        )

        try:
            await asyncio.wait_for(collector_task, timeout=10.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

        full_text = "".join(text_parts)
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
                )


# ── Helpers ────────────────────────────────────────────


async def _safe_send(ws: WebSocket, data: dict) -> None:
    """Send JSON over WebSocket, silently ignoring disconnect errors."""
    try:
        await ws.send_text(json.dumps(data, ensure_ascii=False))
    except Exception:
        pass

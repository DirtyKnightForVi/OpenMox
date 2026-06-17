"""
Shared test helpers — reusable utilities for both conftest.py and test files.

These are PURE utility functions with NO pytest dependency.
Importable as a regular Python module from test files.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Optional

# ── Paths ────────────────────────────────────────────

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
TEST_PROJECT = BACKEND_DIR.parent / "TestProject"
TEMPLATE_DIR = BACKEND_DIR / "experiment" / "test_project_template"
DATA_DIR = BACKEND_DIR / "data"
LOG_DIR = BACKEND_DIR.parent / "logs"

# ── Config ───────────────────────────────────────────

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6480"))
BASE_URL = "http://localhost:8000"


# ═══════════════════════════════════════════════════════════
# EventCollector
# ═══════════════════════════════════════════════════════════


class EventCollector:
    """Collect WebSocket events with assertion helpers + dump on failure."""

    def __init__(self):
        self.events: list[dict] = []
        self._types: list[str] = []

    def add(self, event: dict) -> None:
        self.events.append(event)
        self._types.append(event.get("type", "?"))

    @property
    def event_types(self) -> list[str]:
        return self._types

    def has_type(self, event_type: str) -> bool:
        return event_type in self._types

    def has_sequence(self, *types: str) -> bool:
        seq = list(types)
        idx = 0
        for t in self._types:
            if idx < len(seq) and t == seq[idx]:
                idx += 1
        return idx == len(seq)

    def text_content(self) -> str:
        parts = []
        for e in self.events:
            if e.get("type") == "TEXT_BLOCK_DELTA":
                parts.append(e.get("delta", ""))
        return "".join(parts)

    def count(self, event_type: str) -> int:
        return self._types.count(event_type)

    def agents_seen(self) -> set[str]:
        return {
            e.get("_agent_id", "")
            for e in self.events if e.get("_agent_id")
        }

    def has_completed(self) -> bool:
        """True if agent finished normally (REPLY_END) or needs permission
        confirmation (REQUIRE_USER_CONFIRM)."""
        return self.has_type("REPLY_END") or self.has_type("REQUIRE_USER_CONFIRM")

    def first_of(self, event_type: str) -> dict | None:
        for e in self.events:
            if e.get("type") == event_type:
                return e
        return None

    def dump(self, limit: int = 30) -> str:
        lines = [
            f"  Events collected: {len(self.events)}",
            f"  Event types: {self._types[:50]}",
        ]
        key_events = [
            e for e in self.events
            if e.get("type") in (
                "human_message", "REPLY_START", "REPLY_END",
                "system_message", "TOOL_CALL_END", "TOOL_RESULT_END",
            )
        ]
        for e in key_events[:10]:
            t = e.get("type")
            agent = e.get("_agent_id", "")
            content = ""
            if t == "human_message":
                content = str(e.get("content", ""))[:80]
            elif t == "system_message":
                content = str(e.get("content", ""))[:80]
            lines.append(f"    [{t}] agent={agent} {content}")
        if self.events:
            last = self.events[-1]
            lines.append(f"  Last event: {last.get('type')}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# WebSocket helpers
# ═══════════════════════════════════════════════════════════


async def ws_connect(
    uri: str = "ws://localhost:8000/ws",
    timeout: float = 10.0,
):
    """Connect WebSocket and consume handshake messages."""
    import websockets
    ws = await asyncio.wait_for(
        websockets.connect(uri, ping_interval=30),
        timeout=timeout,
    )
    for _ in range(2):
        try:
            await asyncio.wait_for(ws.recv(), timeout=3.0)
        except asyncio.TimeoutError:
            break
    return ws


async def ws_send_and_collect(
    ws,
    msg: dict,
    collect_until: str = "REPLY_END",
    timeout: float = 120.0,
) -> EventCollector:
    """Send a WS message and collect events until target type.

    Stops early on: REPLY_END (normal), REQUIRE_USER_CONFIRM (agent blocked
    on permission), system_message (error), or 2× silent timeout streaks.
    """
    STOP_TYPES = {"REPLY_END", "REQUIRE_USER_CONFIRM", "system_message"}
    ERROR_TYPES = {"ConnectionClosedError", "ConnectionClosedOK"}
    collector = EventCollector()
    await ws.send(json.dumps(msg, ensure_ascii=False))

    deadline = time.time() + timeout
    silent_streaks = 0
    MAX_SILENT_STREAKS = 6  # 6 × 10s = 60s silence before giving up

    while time.time() < deadline:
        remaining = deadline - time.time()
        recv_timeout = min(10.0, remaining)
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=recv_timeout)
            silent_streaks = 0
        except asyncio.TimeoutError:
            silent_streaks += 1
            # If we've received events, keep waiting even through silence
            # (agent thinking / tool execution can take 30-60s)
            if collector.events and silent_streaks < MAX_SILENT_STREAKS:
                continue
            if silent_streaks >= 2 and not collector.events:
                break  # no events at all → connection likely dead
            if silent_streaks >= MAX_SILENT_STREAKS:
                break  # too long silent even with events
            continue
        except Exception:
            # WS disconnected — stop collecting
            break
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        collector.add(event)
        if event.get("type") in STOP_TYPES:
            break
    return collector


# ═══════════════════════════════════════════════════════════
# Command builder
# ═══════════════════════════════════════════════════════════


def make_command(window_id: str, project_path: str, command: str) -> dict:
    """Build a standard pilotdeck-command dict."""
    return {
        "type": "pilotdeck-command",
        "command": command,
        "options": {
            "sessionKey": window_id,
            "sessionId": window_id,
            "projectPath": project_path,
            "cwd": project_path,
        },
    }

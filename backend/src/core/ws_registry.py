"""
WebSocket + session registry — window_id → (WebSocket, project_path) mapping.

Used by WakeupDispatcher (and future async paths) to push agent
events back to the correct browser connection when the wake-up
originates from a background trigger (scheduler, BG task completion)
rather than a direct user message.

Thread-safe via asyncio.Lock.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import WebSocket


@dataclass
class SessionInfo:
    ws: "WebSocket"
    project_path: str


_registry: dict[str, SessionInfo] = {}
_lock = asyncio.Lock()


async def register(
    window_id: str,
    ws: "WebSocket",
    project_path: str = "",
) -> None:
    """Register a WebSocket + project_path for a window.

    Overwrites any existing registration — only one WebSocket per
    window is allowed.
    """
    async with _lock:
        _registry[window_id] = SessionInfo(ws=ws, project_path=project_path)


async def unregister(window_id: str) -> None:
    """Remove the registration for a window."""
    async with _lock:
        _registry.pop(window_id, None)


async def get_ws(window_id: str) -> "WebSocket | None":
    """Return the WebSocket registered for window_id, or None."""
    async with _lock:
        info = _registry.get(window_id)
        return info.ws if info else None


async def get_project_path(window_id: str) -> str | None:
    """Return the project_path registered for window_id, or None."""
    async with _lock:
        info = _registry.get(window_id)
        return info.project_path if info else None


async def active_sessions() -> list[str]:
    """Return all currently registered window IDs."""
    async with _lock:
        return list(_registry.keys())

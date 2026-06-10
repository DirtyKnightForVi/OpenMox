"""
OpenMoxWorkspaceManager -- returns a LocalWorkspace bound to the project root.

All agents in a project share the same workdir (the project root itself).
No per-agent workspace isolation -- our four-layer permission system handles
file access control at the tool level, not the filesystem level.

When we later need per-agent sandboxing (Phase 3), we can switch to
DockerWorkspace or custom LocalWorkspace with chroot-like workdirs.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from agentscope.app.workspace_manager import WorkspaceManagerBase
from agentscope.workspace import LocalWorkspace
from agentscope._logging import logger

if TYPE_CHECKING:
    from typing import Self


class OpenMoxWorkspaceManager(WorkspaceManagerBase):
    """Minimal workspace manager -- every agent gets the project root.

    The ``workdir`` is always ``project_root`` regardless of agent_id.
    Multiple agents sharing one workspace is intentional: OpenMox's
    four-layer permission system (PermissionEngine rules) gates file
    access at the tool level, so filesystem isolation is unnecessary.
    """

    def __init__(
        self,
        project_root: str | Path,
        ttl: float = 3600.0,
    ) -> None:
        self._project_root = os.path.abspath(str(project_root))
        self._ttl = ttl
        self._cache: dict[str, tuple[LocalWorkspace, float]] = {}
        self._lock = asyncio.Lock()

    async def get_workspace(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
        workspace_id: str,
    ) -> LocalWorkspace:
        """Return a cached or newly-built workspace for ``workspace_id``."""
        async with self._lock:
            now = time.monotonic()
            cached = self._cache.get(workspace_id)
            if cached is not None:
                ws, _ = cached
                self._cache[workspace_id] = (ws, now)
                return ws

        ws = LocalWorkspace(
            workspace_id=workspace_id,
            workdir=self._project_root,
        )
        await ws.initialize()
        async with self._lock:
            self._cache[workspace_id] = (ws, time.monotonic())
        return ws

    async def create_workspace(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
    ) -> LocalWorkspace:
        """Create a workspace -- same as get, all agents share project root."""
        ws = LocalWorkspace(workdir=self._project_root)
        await ws.initialize()
        async with self._lock:
            self._cache[ws.workspace_id] = (ws, time.monotonic())
        return ws

    async def close(self, workspace_id: str) -> None:
        async with self._lock:
            entry = self._cache.pop(workspace_id, None)
        if entry is not None:
            try:
                await entry[0].close()
            except Exception:
                logger.exception("Failed to close workspace %s", workspace_id)

    async def close_all(self) -> None:
        async with self._lock:
            entries = list(self._cache.values())
            self._cache.clear()
        if entries:
            await asyncio.gather(
                *(ws.close() for ws, _ in entries),
                return_exceptions=True,
            )

    async def __aenter__(self) -> "Self":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close_all()

"""
OpenMox Dispatcher wrappers — add retry logic to AgentScope's dispatchers.

AgentScope's WakeupDispatcher._loop and CancelDispatcher._loop exit on
the first Pub/Sub connection error, which happens when a Docker-bridged
Redis connection is idle too long.

These wrappers override _loop with a retry-on-exception pattern
(exponential backoff: 1s → 2s → 4s → … max 60s, then reset).
"""

from __future__ import annotations

import asyncio

from agentscope.app._manager import WakeupDispatcher, CancelDispatcher
from ..core.logging import get_logger

log = get_logger(__name__)


class RetryableWakeupDispatcher(WakeupDispatcher):
    """WakeupDispatcher with retry on Pub/Sub disconnection."""

    async def _loop(self, ready: asyncio.Event) -> None:
        """Wrap the parent's loop with exponential-backoff retry."""
        delay = 1.0
        while True:
            try:
                async for _signal in self._bus.subscribe_wakeup_signal(
                    on_ready=ready.set if not ready.is_set() else None,
                ):
                    await self._drain_and_dispatch()
            except asyncio.CancelledError:
                return
            except Exception:
                delay = min(delay, 60.0)
                log.debug(
                    "WakeupDispatcher: Pub/Sub dropped, retrying in %.1fs",
                    delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60.0)


class RetryableCancelDispatcher(CancelDispatcher):
    """CancelDispatcher with retry on Pub/Sub disconnection."""

    async def _loop(self, ready: asyncio.Event) -> None:
        """Wrap the parent's loop with exponential-backoff retry."""
        delay = 1.0
        while True:
            try:
                async for session_id in self._bus.session_subscribe_cancel(
                    on_ready=ready.set if not ready.is_set() else None,
                ):
                    self._cancel_local(session_id)
            except asyncio.CancelledError:
                return
            except Exception:
                delay = min(delay, 60.0)
                log.debug(
                    "CancelDispatcher: Pub/Sub dropped, retrying in %.1fs",
                    delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60.0)

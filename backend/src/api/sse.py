"""
SSE endpoint — streams agent session events to the frontend.

Replaces our old self-built ``_collect()`` pipeline in chat.py.
The frontend opens one EventSource per running agent to receive
THINKING, TOOL_CALL, TOOL_RESULT, and TEXT events in real time
for the task panel.

Uses agentscope's ``message_bus.subscribe()`` (Redis Pub/Sub), identical
to the framework's own ``GET /sessions/{sid}/stream`` SSE endpoint.
"""
import asyncio
import json
import time

from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..core.logging import get_logger

log = get_logger(__name__)

sse_router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@sse_router.get("/{session_id}/stream")
async def stream_session(
    session_id: str,
    agent_id: str = Query(description="Agent the session belongs to"),
    project_path: str = Query(default=".", description="Project root path"),
):
    """Subscribe to an agent session's live event stream (SSE).

    First replays buffered events from the replay log, then streams
    live events as they are produced by ChatService.run().  A heartbeat
    comment (``:``) is sent every 30s.

    Frontend connects here per agent to populate the task panel with
    real-time THINKING / TOOL_CALL / TOOL_RESULT events.
    """
    from main import app as _app

    storage = getattr(_app.state, "storage", None)
    message_bus = getattr(_app.state, "message_bus", None)

    if not storage or not message_bus:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Compute user_id from project_path (matches _ensure_project_team)
    import hashlib
    project_hash = hashlib.md5(project_path.encode()).hexdigest()[:8]
    user_id = f"openmox:{project_hash}"

    existing = await storage.get_session(user_id, agent_id, session_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )

    from agentscope.app.message_bus import MessageBusKeys

    events_key = MessageBusKeys.session_events(session_id)

    async def _event_generator():
        # 1. Replay buffered events
        try:
            for _entry_id, event in await message_bus.log_read(
                events_key,
                max_count=200,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception:
            pass

        # 2. Live subscription via background feeder
        queue: asyncio.Queue = asyncio.Queue()

        async def _feeder():
            try:
                async for evt in message_bus.subscribe(
                    events_key,
                ):
                    await queue.put(
                        {k: v for k, v in evt.items() if k != "_entry_id"},
                    )
            except asyncio.CancelledError:
                pass
            finally:
                await queue.put(None)

        feeder_task = asyncio.create_task(_feeder(), name=f"sse-feeder:{session_id}")

        last_heartbeat = time.monotonic()
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Heartbeat
                    now = time.monotonic()
                    if now - last_heartbeat >= 30:
                        yield ":\n\n"
                        last_heartbeat = now
                    continue

                if item is None:
                    break

                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        finally:
            feeder_task.cancel()
            try:
                await feeder_task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

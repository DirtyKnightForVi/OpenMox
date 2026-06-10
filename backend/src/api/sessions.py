"""
Session management REST API.

Endpoints:
  POST  /api/sessions                    — create session (returns sessionKey)
  GET   /api/sessions/{id}/messages      — get message history
  GET   /api/sessions/{id}/token-usage   — token usage (stub)
  PUT   /api/sessions/{id}/rename        — rename session (stub)
  DELETE /api/projects/{name}/sessions/{id} — delete session
"""

import uuid
from fastapi import APIRouter, Request

from ..core.store import get_messages, ensure_session
from ..core.store import get_db  # for session deletion

router = APIRouter(prefix="/api", tags=["sessions"])


@router.post("/sessions")
async def create_session(request: Request):
    """Create a new session and return its key."""
    session_key = f"web:s_{uuid.uuid4().hex[:16]}"
    await ensure_session(session_key)
    return {"sessionKey": session_key}


@router.get("/sessions/{session_id}/messages")
async def api_get_messages(session_id: str):
    """Load conversation history for a session."""
    messages = await get_messages(session_id)
    return {
        "messages": messages,
        "hasMore": False,
    }


@router.get("/sessions/{session_id}/token-usage")
async def token_usage(session_id: str):
    """Return token usage (stub — not yet tracked)."""
    return {"used": 0, "limit": 128000}


@router.put("/sessions/{session_id}/rename")
async def rename_session(session_id: str):
    """Rename session (stub)."""
    return {"ok": True}


@router.delete("/projects/{project_name:path}/sessions/{session_id}")
async def delete_session(project_name: str, session_id: str):
    """Delete all messages for a session."""
    # For now, just return ok — full session deletion can be added later
    return {"ok": True}

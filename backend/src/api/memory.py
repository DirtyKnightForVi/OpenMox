"""
Memory REST API — list, edit, pin/delete entries; trigger reflection; rollback snapshots.

Endpoints:
  GET  /api/memory/{agent_id}                  — list memories
  PATCH /api/memory/{agent_id}/{entry_id}       — edit/pin/delete entry
  POST /api/memory/{agent_id}/reflect?scope=quick — manual reflection trigger
  POST /api/memory/{agent_id}/reflect?scope=shendu
  POST /api/memory/project/reflect?scope=quick    — project-wide reflection
  POST /api/memory/{agent_id}/rollback/{snapshot_id} — rollback snapshot
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

from ..core import store as mem_store
from ..core.dream_engine import reflect

router = APIRouter(prefix="/api", tags=["memory"])


class MemoryPatch(BaseModel):
    content: str | None = None
    importance: float | None = None
    pinned: int | None = None
    deprecated: int | None = None


@router.get("/memory/{agent_id}")
async def list_memories(
    agent_id: str,
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    scope: str = Query(default=None),
):
    """List memory entries for an agent."""
    entries = await mem_store.list_memory(agent_id, scope=scope, limit=limit, offset=offset)
    return {"entries": entries, "total": len(entries)}


@router.patch("/memory/{agent_id}/{entry_id}")
async def update_memory(
    agent_id: str,
    entry_id: int,
    patch: MemoryPatch,
):
    """Edit, pin, or deprecate a memory entry."""
    updates = {k: v for k, v in patch.model_dump().items() if v is not None}
    if not updates:
        return {"ok": False, "error": "no fields to update"}
    updated = await mem_store.update_memory(entry_id, **updates)
    if not updated:
        return {"ok": False, "error": f"entry {entry_id} not found"}
    return {"ok": True, "entry": updated}


@router.post("/memory/{agent_id}/reflect")
async def trigger_reflect(
    agent_id: str,
    scope: str = Query(default="quick"),
    project_path: str = Query(default="."),
    window_id: str = Query(default=""),
):
    """Manually trigger quick reflection or shendu for one agent."""
    if scope not in ("quick", "shendu", "manual"):
        return {"ok": False, "error": f"unknown scope: {scope}"}
    result = await reflect(
        agent_id=agent_id, project_id=project_path,
        scope=scope, window_id=window_id,
    )
    return {"ok": True, **result}


@router.post("/memory/project/reflect")
async def trigger_reflect_all(
    scope: str = Query(default="quick"),
    project_path: str = Query(default="."),
):
    """Trigger reflection for all agents in the project."""
    from ..dao import ConfigDAO
    dao = ConfigDAO(project_path)
    agents = dao.list_agents()
    results = {}
    for a in agents:
        try:
            r = await reflect(agent_id=a.id, project_id=project_path, scope=scope)
            results[a.id] = r
        except Exception as e:
            results[a.id] = {"error": str(e)}
    return {"ok": True, "results": results}


@router.post("/memory/{agent_id}/sync")
async def sync_memory_to_file(
    agent_id: str,
    project_path: str = Query(default="."),
    scope: str = Query(default="private"),
):
    """Sync SQLite memory entries → MEMORY.md Markdown file.

    Reads all non-deprecated entries for the agent (private scope)
    or all shared entries (shared scope) and writes them to the
    corresponding Markdown file.
    """
    from ..memory.sync import sync_entries_to_markdown
    count = await sync_entries_to_markdown(
        agent_id=agent_id,
        project_root=project_path,
        scope=scope,
    )
    return {"ok": True, "entries_written": count}


@router.post("/memory/project/sync")
async def sync_project_memo(
    project_path: str = Query(default="."),
):
    """Sync shared memories → .Project/PROJECT_MEMO.md."""
    from ..memory.sync import sync_project_memo
    count = await sync_project_memo(project_root=project_path)
    return {"ok": True, "entries_written": count}


@router.post("/memory/{agent_id}/rollback/{snapshot_id}")
async def rollback_memory(
    agent_id: str,
    snapshot_id: int,
):
    """Rollback to a specific dream snapshot."""
    ok = await mem_store.rollback_snapshot(snapshot_id)
    if not ok:
        return {"ok": False, "error": f"snapshot {snapshot_id} not found"}
    return {"ok": True, "snapshot_id": snapshot_id}

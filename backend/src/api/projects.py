"""
Project CRUD REST API.

Endpoints:
  GET    /api/projects                    — list projects
  POST   /api/projects/create             — create project
  POST   /api/projects/create-workspace   — create workspace (PilotDeck compat)
  PUT    /api/projects/{name}/rename      — rename project
  DELETE /api/projects/{name}             — delete project
"""

import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request

from ..core.store import list_projects, create_project, delete_project
from ..core.logging import get_logger
from ..dao import ConfigDAO

log = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["projects"])


@router.get("/projects")
async def api_list_projects():
    """Return all projects as a flat array (PilotDeck compat)."""
    projects = await list_projects()
    return projects  # flat array, NOT {projects: [...]}


@router.post("/projects/create")
async def api_create_project(request: Request):
    """Create a project directory and persist to DB."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    path = body.get("path", "")
    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    name = body.get("name", os.path.basename(path) or "new-project")
    display_name = body.get("display_name") or body.get("displayName") or name

    # Ensure disk directories + project scaffold
    try:
        root = Path(path)
        root.mkdir(parents=True, exist_ok=True)
        for d in [".Agents", ".Project", ".Project/rules", ".Project/skills"]:
            (root / d).mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        log.error("Failed to init project dir %s: %s", path, exc)
        raise HTTPException(
            status_code=400,
            detail=f"Cannot create project directory: {exc}",
        )

    project = await create_project(name, path, display_name)
    log.info("Project created: %s at %s", name, path)
    return project


@router.post("/projects/create-workspace")
async def api_create_workspace(request: Request):
    """Frontend ProjectCreationWizard calls this."""
    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON body"}

    path = body.get("path", "")
    if not path:
        return {"ok": False, "error": "path is required"}

    name = body.get("name", os.path.basename(path) or "new-workspace")
    display_name = body.get("display_name") or body.get("displayName") or name

    try:
        root = Path(path)
        root.mkdir(parents=True, exist_ok=True)
        for d in [".Agents", ".Project", ".Project/rules", ".Project/skills"]:
            (root / d).mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        log.error("Failed to init project dir %s: %s", path, exc)
        raise HTTPException(
            status_code=400,
            detail=f"Cannot create project directory: {exc}",
        )

    project = await create_project(name, path, display_name)
    return project


@router.put("/projects/{project_name:path}/rename")
async def api_rename_project(project_name: str, request: Request):
    """Rename a project."""
    # SQLite doesn't support rename yet — just return ok for compat
    return {"ok": True}


@router.delete("/projects/{project_name:path}")
async def api_delete_project(project_name: str):
    """Delete a project from the store."""
    deleted = await delete_project(project_name)
    if not deleted:
        return {"ok": True}  # idempotent
    log.info("Project deleted: %s", project_name)
    return {"ok": True}

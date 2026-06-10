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
from fastapi import APIRouter, Request

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
    body = await request.json()
    path = body.get("path", body.get("fullPath", ""))
    name = os.path.basename(path) or body.get("name", "new-project")

    # Ensure disk directories + project scaffold
    root = Path(path)
    ConfigDAO.init_project(root)

    project = await create_project(name, path, body.get("displayName", name))
    log.info("Project created: %s at %s", name, path)
    return project


@router.post("/projects/create-workspace")
async def api_create_workspace(request: Request):
    """Frontend ProjectCreationWizard calls this."""
    body = await request.json()
    path = body.get("path", "")
    name = os.path.basename(path) or body.get("name", "new-workspace")

    root = Path(path)
    ConfigDAO.init_project(root)

    project = await create_project(name, path, body.get("displayName", name))
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

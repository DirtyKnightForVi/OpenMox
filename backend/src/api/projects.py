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


def _init_momo_if_needed(project_path: str) -> None:
    """Create a default momo agent in a freshly scaffolded project.

    Called right after :func:`api_create_project` has created the
    ``.Agents/`` and ``.Project/`` directories.  Uses the first
    available agent template and marks it as momo.  Idempotent —
    does nothing if momo already exists.
    """
    dao = ConfigDAO(project_path)
    if dao.get_momo_id():
        return  # already initialised

    templates = ConfigDAO.list_templates()
    if not templates:
        log.warning("No agent templates found — skipping momo init for %s", project_path)
        return

    template_id = templates[0].id
    try:
        cfg = dao.create_agent(
            agent_id="momo",
            template_id=template_id,
            name="momo",
        )
        log.info(
            "Project %s: auto-created momo agent from template %s",
            project_path, template_id,
        )
    except Exception as exc:
        log.warning("Failed to auto-create momo for %s: %s", project_path, exc)


@router.get("/projects")
async def api_list_projects():
    """Return all projects as a flat array (PilotDeck compat)."""
    projects = await list_projects()
    return projects  # flat array, NOT {projects: [...]}


@router.post("/projects/create")
async def api_create_project(request: Request):
    """Create a project directory, optionally with selected agent templates.

    Body:
        path: str              — absolute project path (required)
        name: str              — project name (default: basename of path)
        display_name: str      — display name (default: name)
        selected_templates: list[str] | None
            — template IDs to instantiate (e.g. ["product-manager", "dev-manager"]).
              If provided, agents are created from these templates and a
              .Project/team.yaml is auto-generated with momo as leader.
              If omitted, only a momo agent is auto-created.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    path = body.get("path", "")
    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    name = body.get("name", os.path.basename(path) or "new-project")
    display_name = body.get("display_name") or body.get("displayName") or name
    selected_templates: list[str] | None = body.get("selected_templates")
    template_id: str | None = body.get("template")  # preset template name

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

    dao = ConfigDAO(path)

    # Resolve preset template → selected_templates
    if template_id and not selected_templates:
        tmpl = ConfigDAO.get_project_template(template_id)
        if tmpl:
            selected_templates = tmpl.get("agents", [])
            log.info("Project %s: using template %s → agents=%s",
                     name, template_id, selected_templates)
        else:
            log.warning("Project %s: template %s not found", name, template_id)

    if selected_templates:
        # ── User selected specific templates ──
        # 1. Create momo first
        _init_momo_if_needed(path)
        momo_id = dao.get_momo_id()

        # 2. Instantiate each selected template
        created_ids: list[str] = []
        for tmpl_id in selected_templates:
            try:
                cfg = dao.create_agent(
                    agent_id=tmpl_id,     # use template id as agent id
                    template_id=tmpl_id,
                )
                created_ids.append(cfg.id)
                log.info("Project %s: created agent %s from template %s",
                         name, cfg.id, tmpl_id)
            except Exception as exc:
                log.warning("Project %s: failed to create agent from %s: %s",
                            name, tmpl_id, exc)

        # 3. Write team.yaml — momo as leader, all created agents as members
        if momo_id:
            all_members = [momo_id] + created_ids
            dao.write_team_yaml(momo_id, all_members)
            log.info("Project %s: team.yaml written — leader=%s members=%s",
                     name, momo_id, all_members)
    else:
        # ── Legacy: auto-create only momo ──
        _init_momo_if_needed(path)

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

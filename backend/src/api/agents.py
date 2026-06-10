"""
Agent CRUD REST API.

Endpoints:
  GET    /api/agents              — list agents in default project
  GET    /api/agents/{project_key:path} — list agents in a project
  POST   /api/agents/{project_key:path} — create agent
  DELETE /api/agents/{project_key:path}/{agent_id} — delete agent
  PATCH  /api/agents/{project_key:path}/{agent_id} — update agent
  GET    /api/agent-templates     — agent templates from Agent_Sets/
  GET    /api/agents/runtime-config — PilotDeck compat
"""

from dataclasses import asdict
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException

from ..dao import ConfigDAO
from ..core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["agents"])


def _resolve_path(project_key: str) -> Path:
    p = Path(project_key)
    return p if p.is_absolute() else Path.cwd()


# ── Agent CRUD ─────────────────────────────────────────


@router.get("/agents")
async def list_default_agents():
    """List agents in current directory."""
    dao = ConfigDAO(Path.cwd())
    return [asdict(a) for a in dao.list_agents()]


@router.get("/agents/{project_key:path}")
async def list_agents(project_key: str):
    """List agents in a project."""
    dao = ConfigDAO(_resolve_path(project_key))
    return [asdict(a) for a in dao.list_agents()]


@router.post("/agents/{project_key:path}")
async def create_agent(project_key: str, request: Request):
    """Create an agent in a project."""
    body = await request.json()
    # Accept both 'agent_id'/'template_id' (frontend) and 'id'/'template' (legacy)
    agent_id = (body.get("agent_id") or body.get("id") or "").strip()
    template_id = (body.get("template_id") or body.get("template") or agent_id).strip()
    if not agent_id:
        raise HTTPException(400, "id is required")

    dao = ConfigDAO(_resolve_path(project_key))
    try:
        config = dao.create_agent(
            agent_id=agent_id,
            template_id=template_id,
            name=body.get("name"),
            avatar=body.get("avatar"),
            description=body.get("description"),
            system_override=body.get("system"),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    log.info("Agent created: %s (template=%s)", agent_id, template_id)
    return {"ok": True, "agent": {"id": agent_id, "name": config.name}}


@router.delete("/agents/{project_key:path}/{agent_id}")
async def delete_agent(project_key: str, agent_id: str):
    """Delete an agent."""
    dao = ConfigDAO(_resolve_path(project_key))
    deleted = dao.delete_agent(agent_id)
    if not deleted:
        raise HTTPException(404, "Agent not found")
    log.info("Agent deleted: %s", agent_id)
    return {"ok": True}


@router.patch("/agents/{project_key:path}/{agent_id}")
async def update_agent(project_key: str, agent_id: str, request: Request):
    """Update an agent's config fields."""
    dao = ConfigDAO(_resolve_path(project_key))
    existing = dao.get_agent(agent_id)
    if not existing:
        raise HTTPException(404, "Agent not found")

    body = await request.json()
    # Re-read raw YAML for update (DAO's dataclass is read-only for now)
    yaml_path = dao.agents_dir / agent_id / "agent.yaml"
    data = ConfigDAO._read_yaml(yaml_path)

    for field in ("name", "description", "avatar", "system"):
        if field in body:
            data[field] = body[field]
    if "rules" in body:
        data["rules"] = body["rules"]
    if "skills" in body:
        data["skills"] = body["skills"]

    ConfigDAO._write_yaml(yaml_path, data)
    log.info("Agent updated: %s", agent_id)
    return {"ok": True}


# ── Templates ──────────────────────────────────────────


@router.get("/agent-templates")
async def list_templates():
    """Agent templates from Agent_Sets/."""
    return [asdict(t) for t in ConfigDAO.list_templates()]


# ── Runtime config (PilotDeck compat) ──────────────────


@router.get("/agents/runtime-config")
async def runtime_config():
    return {
        "pilotdeck": {"provider": "deepseek"},
        "permissions": {
            "skipPermissions": True,
            "effectiveMode": "bypassPermissions",
        },
    }

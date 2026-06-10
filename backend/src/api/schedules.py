"""Schedule CRUD REST API.

Endpoints:
  GET    /api/schedules           — list all schedules
  POST   /api/schedules           — create a schedule
  DELETE /api/schedules/{id}      — delete a schedule
"""

from fastapi import APIRouter, Request, HTTPException

from ..schedule.scheduler import add_schedule, remove_schedule, list_schedules
from ..core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["schedules"])


@router.get("/schedules")
async def api_list_schedules():
    """List all active cron schedules."""
    return {"schedules": list_schedules()}


@router.post("/schedules")
async def api_create_schedule(request: Request):
    """Create a recurring schedule.

    Body: {
        "agent_id": "pm-secretary",
        "project_root": ".",
        "cron": "0 9 * * *",
        "message": "汇总昨日进展"
    }
    """
    body = await request.json()
    agent_id = body.get("agent_id", "")
    project_root = body.get("project_root", ".")
    cron = body.get("cron", "")
    message = body.get("message", "")

    if not agent_id or not cron or not message:
        raise HTTPException(400, "agent_id, cron, and message are required")

    schedule_id = f"sch_{agent_id}_{len(list_schedules())}"
    add_schedule(schedule_id, agent_id, project_root, cron, message)
    log.info("Schedule created: %s", schedule_id)
    return {"ok": True, "id": schedule_id}


@router.delete("/schedules/{schedule_id}")
async def api_delete_schedule(schedule_id: str):
    """Delete a schedule."""
    removed = remove_schedule(schedule_id)
    if not removed:
        raise HTTPException(404, "Schedule not found")
    return {"ok": True}

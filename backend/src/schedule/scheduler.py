"""Heartbeat scheduler — APScheduler-based cron trigger for agents."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..core.logging import get_logger

log = get_logger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    """Start the background scheduler. Called once at app startup."""
    scheduler.start()
    log.info("Scheduler started")


def stop_scheduler() -> None:
    """Shut down the scheduler. Called at app shutdown."""
    scheduler.shutdown(wait=False)
    log.info("Scheduler stopped")


def add_schedule(
    schedule_id: str,
    agent_id: str,
    project_root: str,
    cron_expression: str,
    message: str,
) -> None:
    """Add a recurring cron job that triggers an agent.

    Args:
        schedule_id: Unique identifier for this schedule.
        agent_id: The agent to wake up.
        project_root: Project path for context loading.
        cron_expression: Cron expression (e.g. "0 9 * * *" for 9am daily).
        message: The message to send to the agent.
    """

    async def _job():
        log.info("Schedule %s: triggering agent %s", schedule_id, agent_id)
        from ..dao import ConfigDAO
        from ..core.agent_factory import get_agent
        from agentscope.message import Msg

        dao = ConfigDAO(project_root)
        cfg = dao.get_agent(agent_id)
        if not cfg:
            log.error("Schedule %s: agent %s not found", schedule_id, agent_id)
            return

        agent = get_agent(
            agent_id,
            cfg.system,
            skill_dirs=dao.get_skill_dirs(agent_id),
            onboarding_context=dao.get_onboarding_context(),
        )
        result = await agent.reply(
            Msg(role="user", content=message, name="system")
        )
        log.info(
            "Schedule %s: agent %s replied (%d chars)",
            schedule_id,
            agent_id,
            len(result.get_text_content()),
        )

    scheduler.add_job(
        _job,
        trigger=CronTrigger.from_crontab(cron_expression),
        id=schedule_id,
        replace_existing=True,
    )
    log.info(
        "Schedule added: %s → %s [%s]", schedule_id, agent_id, cron_expression
    )


def remove_schedule(schedule_id: str) -> bool:
    """Remove a schedule by ID. Returns True if it existed."""
    try:
        scheduler.remove_job(schedule_id)
        log.info("Schedule removed: %s", schedule_id)
        return True
    except Exception:
        return False


def list_schedules() -> list[dict]:
    """Return all active schedules."""
    jobs = scheduler.get_jobs()
    return [
        {
            "id": job.id,
            "next_run": str(job.next_run_time) if hasattr(job, 'next_run_time') and job.next_run_time else None,
        }
        for job in jobs
    ]

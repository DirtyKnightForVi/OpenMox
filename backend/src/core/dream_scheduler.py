"""Dream/relection scheduler — periodic jobs for quick reflection + shendu (慎独).

Runs under the existing APScheduler started in src/schedule/scheduler.py.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from ..core.logging import get_logger

log = get_logger(__name__)

# ── Configurable thresholds ─────────────────────────

QUICK_REFLECT_INTERVAL_SECS = 10 * 60    # scan every 10 min
QUICK_IDLE_THRESHOLD_SECS = 10 * 60      # 10 min idle → quick reflect
SHENDU_WINDOW_START = 23                 # 23:00
SHENDU_WINDOW_END = 6                    # 06:00
SHENDU_IDLE_THRESHOLD_SECS = 30 * 60     # 30 min idle in window → shendu
MIN_ENTRIES_BEFORE_DREAM = 10            # don't dream if fewer than this many entries


def _register_dream_jobs(scheduler, project_root: str = ".") -> None:
    """Register periodic dream/reflection jobs on the given scheduler.

    Called once at application startup.
    """

    async def _quick_reflect_cycle():
        """Scan all agents: if idle > threshold, run quick reflection."""
        try:
            from ..dao import ConfigDAO
            from ..core.dream_engine import reflect
            from ..core.store import get_db

            dao = ConfigDAO(project_root)
            agents = dao.list_agents()
            db = await get_db()

            for a in agents:
                # Check idle time: last message from/to this agent
                cursor = await db.execute(
                    """SELECT MAX(timestamp) FROM messages
                       WHERE speaker_id = ? OR
                             (speaker_type = 'human' AND content LIKE '%@' || ? || '%')""",
                    (a.id, a.id),
                )
                row = await cursor.fetchone()
                last_ts = row[0] if row and row[0] else 0
                now = int(time.time())
                idle = now - last_ts if last_ts else 99999

                if idle < QUICK_IDLE_THRESHOLD_SECS:
                    continue

                log.info("Dream: quick reflect for %s (idle %ds)", a.id, idle)
                try:
                    await reflect(agent_id=a.id, project_id=project_root, scope="quick")
                except Exception as e:
                    log.warning("Dream: quick reflect failed for %s: %s", a.id, e)
        except Exception as e:
            log.warning("Dream: quick reflect cycle failed: %s", e)

    async def _shendu_check():
        """Check if current time is in shendu window, and if so check each agent."""
        now = datetime.now(timezone.utc)
        hour = now.hour
        in_window = (hour >= SHENDU_WINDOW_START or hour < SHENDU_WINDOW_END)

        if not in_window:
            return

        log.info("Dream: shendu window active (hour=%d)", hour)
        try:
            from ..dao import ConfigDAO
            from ..core.dream_engine import reflect
            from ..core.store import get_db

            dao = ConfigDAO(project_root)
            agents = dao.list_agents()
            db = await get_db()

            for a in agents:
                # Check idle
                cursor = await db.execute(
                    "SELECT MAX(timestamp) FROM messages WHERE speaker_id = ?",
                    (a.id,),
                )
                row = await cursor.fetchone()
                idle = int(time.time()) - (row[0] if row and row[0] else 0)

                if idle < SHENDU_IDLE_THRESHOLD_SECS:
                    continue

                # Check if already dreamed in this window
                cursor2 = await db.execute(
                    """SELECT MAX(created_at) FROM dream_snapshots
                       WHERE agent_id = ? AND rolled_back = 0""",
                    (a.id,),
                )
                snap_row = await cursor2.fetchone()
                if snap_row and snap_row[0]:
                    last_snapshot = datetime.fromisoformat(snap_row[0])
                    # If dreamed in the last 2 hours, skip
                    if (now - last_snapshot).total_seconds() < 7200:
                        continue

                log.info("Dream: shendu for %s (idle %ds)", a.id, idle)
                try:
                    await reflect(agent_id=a.id, project_id=project_root, scope="shendu")
                except Exception as e:
                    log.warning("Dream: shendu failed for %s: %s", a.id, e)
        except Exception as e:
            log.warning("Dream: shendu check failed: %s", e)

    import time
    scheduler.add_job(
        _quick_reflect_cycle,
        trigger=IntervalTrigger(seconds=QUICK_REFLECT_INTERVAL_SECS),
        id="dream-quick-reflect",
        replace_existing=True,
    )
    scheduler.add_job(
        _shendu_check,
        trigger=IntervalTrigger(seconds=300),  # check every 5 min
        id="dream-shendu-check",
        replace_existing=True,
    )
    log.info("Dream jobs registered (quick every %ds, shendu every 5min)",
             QUICK_REFLECT_INTERVAL_SECS)

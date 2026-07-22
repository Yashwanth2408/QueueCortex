from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.sync.manager import SyncManager

JOB_ID = "trinity_incremental_poll"
ROSTER_JOB_ID = "shift_watch_roster_poll"

# Shift Watch needs a much tighter loop than the personal sync: the two
# Trinity buckets it reads from only ever return currently-OPEN tickets, so
# a ticket that closes (or gets picked up and resolved) has to be caught
# promptly or it lingers in the feed looking actionable when it isn't.
# Fixed, not tied to poll_interval_minutes - that setting is about the
# tracked agent's own sync cadence, a separate concern.
ROSTER_POLL_INTERVAL_MINUTES = 3


class Scheduler:
    def __init__(self):
        self._scheduler = AsyncIOScheduler()

    def start(self, sync_manager: SyncManager, poll_interval_minutes: int) -> None:
        self._scheduler.add_job(
            sync_manager.run_scheduled,
            trigger=IntervalTrigger(minutes=poll_interval_minutes),
            id=JOB_ID,
            replace_existing=True,
            max_instances=1,
        )
        self._scheduler.add_job(
            sync_manager.run_roster_sync_now,
            trigger=IntervalTrigger(minutes=ROSTER_POLL_INTERVAL_MINUTES),
            id=ROSTER_JOB_ID,
            replace_existing=True,
            max_instances=1,
        )
        self._scheduler.start()

    def reschedule(self, poll_interval_minutes: int) -> None:
        self._scheduler.reschedule_job(JOB_ID, trigger=IntervalTrigger(minutes=poll_interval_minutes))

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

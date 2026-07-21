from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.sync.manager import SyncManager

JOB_ID = "trinity_incremental_poll"


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
        self._scheduler.start()

    def reschedule(self, poll_interval_minutes: int) -> None:
        self._scheduler.reschedule_job(JOB_ID, trigger=IntervalTrigger(minutes=poll_interval_minutes))

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

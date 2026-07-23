"""Guards against the scheduled poll and a manual 'Sync now' racing each
other, and runs sync work in the background so the API can respond
immediately with a run id the frontend can poll.
"""

import asyncio
import logging

from app.config import Settings
from app.db import SessionLocal
from app.sync.engine import create_pending_run, run_full_backfill, run_incremental_sync
from app.sync.roster_sync import run_roster_sync
from app.trinity_client import TrinityClient

logger = logging.getLogger("sync.manager")


class SyncManager:
    def __init__(self, client: TrinityClient, settings: Settings):
        self._client = client
        self._settings = settings
        self._lock = asyncio.Lock()
        self._active_run_id: int | None = None

    @property
    def is_running(self) -> bool:
        return self._lock.locked()

    @property
    def active_run_id(self) -> int | None:
        """The SyncRun actually holding the lock right now, or None. A
        manual "Sync now" click with wait_if_busy=True creates its SyncRun
        row (status='running') before it's actually running - if it's
        queued behind something else, its row exists but this won't point
        to it yet, which is exactly what /sync/status needs to show
        progress for whichever run is truly executing, not just whichever
        row is newest."""
        return self._active_run_id

    async def trigger(self, mode: str, run_type: str, wait_if_busy: bool = False) -> int:
        """Create the SyncRun row synchronously and kick off the work in the
        background.

        wait_if_busy=False (the scheduled poll's behavior): raises
        RuntimeError immediately if a sync (personal or Shift Watch's
        roster sync - they share one lock so the two never write to
        SQLite at once) is already running, since the next scheduled tick
        will pick it up anyway - no need to queue behind it.

        wait_if_busy=True (manual "Sync now" clicks): never raises for
        that reason - the run is created as 'running' right away and
        _execute simply queues on the same lock, starting the moment
        whatever's currently using it finishes. A user-initiated click
        should always eventually run rather than bounce off a background
        job they don't know is in progress; the frontend already polls
        the run until it completes either way, so there's nothing extra
        to wait for on that end."""
        if not wait_if_busy and self._lock.locked():
            raise RuntimeError("A sync is already running")

        async with SessionLocal() as session:
            run_id = await create_pending_run(session, run_type)

        asyncio.create_task(self._execute(mode, run_id))
        return run_id

    async def _execute(self, mode: str, run_id: int) -> None:
        async with self._lock:
            self._active_run_id = run_id
            try:
                async with SessionLocal() as session:
                    try:
                        if mode == "full":
                            await run_full_backfill(self._client, session, self._settings, run_id)
                        else:
                            await run_incremental_sync(self._client, session, self._settings, run_id)
                    except Exception:  # noqa: BLE001
                        logger.exception("sync run %s failed", run_id)
            finally:
                self._active_run_id = None

    async def run_scheduled(self) -> None:
        try:
            await self.trigger(mode="incremental", run_type="scheduled")
        except RuntimeError:
            logger.info("scheduled sync skipped: a sync is already running")

    async def run_roster_sync_now(self) -> None:
        """Shift Watch's own sync - runs on a separate, more frequent
        schedule than the personal sync (see scheduler.py), plus once
        immediately after a roster CSV upload. Uses the same lock as the
        personal sync (not a second, independent one) so they never run
        concurrently against the same SQLite file; skips rather than blocks
        if one's already in progress - the next tick picks it up anyway."""
        if self._lock.locked():
            return
        async with self._lock:
            async with SessionLocal() as session:
                run_id = await create_pending_run(session, "roster")
                self._active_run_id = run_id
                try:
                    await run_roster_sync(self._client, session, self._settings, run_id)
                except Exception:  # noqa: BLE001
                    logger.exception("roster sync failed")
                finally:
                    self._active_run_id = None

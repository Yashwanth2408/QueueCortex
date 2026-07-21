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

    @property
    def is_running(self) -> bool:
        return self._lock.locked()

    async def trigger(self, mode: str, run_type: str) -> int:
        """Create the SyncRun row synchronously and kick off the work in the
        background. Raises RuntimeError if a sync is already in progress."""
        if self._lock.locked():
            raise RuntimeError("A sync is already running")

        async with SessionLocal() as session:
            run_id = await create_pending_run(session, run_type)

        asyncio.create_task(self._execute(mode, run_id))
        return run_id

    async def _execute(self, mode: str, run_id: int) -> None:
        async with self._lock:
            async with SessionLocal() as session:
                try:
                    if mode == "full":
                        await run_full_backfill(self._client, session, self._settings, run_id)
                    else:
                        await run_incremental_sync(self._client, session, self._settings, run_id)
                except Exception:  # noqa: BLE001
                    logger.exception("sync run %s failed", run_id)

            # Shift Watch: refresh roster agents' open/pending tickets at the
            # same cadence as the personal sync. Its own try/except - a
            # roster-sync failure shouldn't mark the personal SyncRun above
            # as failed, since they're logically independent.
            async with SessionLocal() as session:
                try:
                    await run_roster_sync(self._client, session, self._settings)
                except Exception:  # noqa: BLE001
                    logger.exception("roster sync failed")

    async def run_scheduled(self) -> None:
        try:
            await self.trigger(mode="incremental", run_type="scheduled")
        except RuntimeError:
            logger.info("scheduled sync skipped: a sync is already running")

    async def run_roster_sync_now(self) -> None:
        """Best-effort immediate roster refresh after a CSV upload, so Shift
        Watch isn't stale until the next poll tick. Skips (rather than
        blocking) if a sync is already in progress - the next scheduled tick
        will pick up the new roster anyway."""
        if self._lock.locked():
            return
        async with self._lock:
            async with SessionLocal() as session:
                try:
                    await run_roster_sync(self._client, session, self._settings)
                except Exception:  # noqa: BLE001
                    logger.exception("roster sync (post-upload) failed")

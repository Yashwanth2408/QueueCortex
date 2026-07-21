"""Guards against the scheduled poll and a manual 'Sync now' racing each
other, and runs sync work in the background so the API can respond
immediately with a run id the frontend can poll.
"""

import asyncio
import logging

from app.config import Settings
from app.db import SessionLocal
from app.sync.engine import create_pending_run, run_full_backfill, run_incremental_sync
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

    async def run_scheduled(self) -> None:
        try:
            await self.trigger(mode="incremental", run_type="scheduled")
        except RuntimeError:
            logger.info("scheduled sync skipped: a sync is already running")

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_sync_manager
from app.db import get_session
from app.models import SyncRun, SyncState
from app.schemas import SyncRunOut, SyncRunRequest, SyncStatusOut
from app.sync.engine import add_ticket_by_number  # noqa: F401 (re-export convenience)
from app.sync.manager import SyncManager

router = APIRouter(tags=["sync"])


@router.post("/sync/run", status_code=202)
async def trigger_sync(body: SyncRunRequest, manager: SyncManager = Depends(get_sync_manager)):
    run_type = "manual" if body.mode == "incremental" else "backfill"
    # wait_if_busy=True: a manual click should always eventually run rather
    # than bounce off a background poll it doesn't know is in progress -
    # see the docstring on SyncManager.trigger.
    run_id = await manager.trigger(mode=body.mode, run_type=run_type, wait_if_busy=True)
    return {"sync_run_id": run_id}


@router.get("/sync/runs/{run_id}", response_model=SyncRunOut)
async def get_sync_run(run_id: int, session: AsyncSession = Depends(get_session)):
    run = await session.get(SyncRun, run_id)
    if run is None:
        raise HTTPException(404, "Sync run not found")
    return run


@router.get("/sync/status", response_model=SyncStatusOut)
async def get_sync_status(
    session: AsyncSession = Depends(get_session), manager: SyncManager = Depends(get_sync_manager)
):
    state = await session.get(SyncState, "primary")
    # active_run_id (not "most recent status='running' row") - a manual
    # "Sync now" queued behind an already-running sync creates its row
    # immediately too, so the newest 'running' row isn't necessarily the
    # one actually executing; stale rows from a killed process can also
    # linger as 'running' forever. active_run_id is only ever set to the
    # run genuinely holding the lock right now.
    current_run = await session.get(SyncRun, manager.active_run_id) if manager.active_run_id is not None else None
    return SyncStatusOut(
        last_full_backfill_at=state.last_full_backfill_at if state else None,
        last_incremental_sync_at=state.last_incremental_sync_at if state else None,
        last_incremental_sync_status=state.last_incremental_sync_status if state else None,
        last_incremental_sync_error=state.last_incremental_sync_error if state else None,
        next_poll_at=state.next_poll_at if state else None,
        is_running=manager.is_running,
        current_run=current_run,
    )

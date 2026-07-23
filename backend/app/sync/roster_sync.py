"""Pulls tickets from the two Trinity buckets that define "L2, non-Expo"
tickets - "L2 - Unassigned Tickets" and "L2 - Assigned (New Assigned +
Re-opens)" - into the same local tables the tracked-agent sync uses
(tickets/ticket_events/status_transitions/assignment_events), but always
with `mark_personal=False`, so these tickets never affect Yashwanth's own
Dashboard/Analytics (see `Ticket.is_tracked` in models.py and the
`mark_personal` plumbing in sync/engine.py). This is what powers the
"Shift Watch" feed of tickets held by agents who are off-shift.

Trusting bucket membership entirely (rather than reconstructing the same
level/tag rules locally) is deliberate: the bucket IDs are configurable via
Settings (roster_bucket_unassigned_id / roster_bucket_assigned_id) in case
Trinity's bucket setup ever changes."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import SyncRun, Ticket
from app.settings_store import DEFAULT_ROSTER_BUCKET_ASSIGNED_ID, DEFAULT_ROSTER_BUCKET_UNASSIGNED_ID, get_value
from app.sync.engine import ingest_ticket_for_roster, refresh_roster_ticket_incremental, refresh_ticket_snapshot
from app.sync.timeutil import parse_trinity_dt, utcnow
from app.trinity_client import TrinityClient

ROSTER_SYNC_PAGE_LIMIT = 100


def _apply_progress(run: SyncRun | None, base: dict, checked: int, updated: int, events: int) -> None:
    """Reflects live progress onto the SyncRun row - `base` is the running
    total from phases already finished this run, so the same call works
    whether this is the first bucket or the tail-end supplemental pass."""
    if run is None:
        return
    run.tickets_checked = base["checked"] + checked
    run.tickets_updated = base["updated"] + updated
    run.events_ingested = base["events"] + events


async def _sync_bucket(
    client: TrinityClient,
    session: AsyncSession,
    settings: Settings,
    bucket_id: str,
    now: datetime,
    touched_ids: set[str],
    run: SyncRun | None,
    base: dict,
) -> dict:
    checked = updated = events = 0
    errors: list[str] = []
    cursor = None
    while True:
        try:
            page = await client.list_tickets(
                bucket_id=bucket_id, sort_key="updated_at", sort_dir="desc", limit=ROSTER_SYNC_PAGE_LIMIT, cursor=cursor
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"bucket {bucket_id}: {exc}")
            break

        items = page.get("items", [])
        for item in items:
            checked += 1
            touched_ids.add(item["id"])
            try:
                existing = await session.get(Ticket, item["id"])
                if existing is None:
                    _, ingested = await ingest_ticket_for_roster(client, session, item["id"], settings, now, full=True)
                else:
                    remote_updated = parse_trinity_dt(item["updated_at"])
                    if existing.updated_at_trinity is not None and remote_updated <= existing.updated_at_trinity:
                        _apply_progress(run, base, checked, updated, events)
                        continue
                    ingested = await refresh_roster_ticket_incremental(client, session, item, settings, now)
                updated += 1
                events += ingested
                # Commit per item, not once per bucket - the same lock this
                # sync holds also guards the personal "Sync now" (see
                # sync/manager.py), and per-item commits are what let a live
                # percentage actually move instead of jumping once at the
                # very end.
                _apply_progress(run, base, checked, updated, events)
                await session.commit()
            except Exception as exc:  # noqa: BLE001
                # A failed commit leaves the session unable to run any
                # further statements until rolled back - without this, one
                # bad ticket would silently poison every ticket after it in
                # this same pass.
                await session.rollback()
                errors.append(f"ticket #{item.get('num')}: {exc}")

        cursor = page.get("next_cursor")
        if not cursor:
            break

    return {"checked": checked, "updated": updated, "events": events, "errors": errors}


async def _supplemental_pass(
    client: TrinityClient,
    session: AsyncSession,
    settings: Settings,
    now: datetime,
    touched_ids: set[str],
    run: SyncRun | None,
    base: dict,
) -> dict:
    """The two buckets only ever return currently-OPEN tickets (baked into
    their Trinity rule_tree), so a roster ticket that quietly closes - or
    gets picked up and resolved - simply stops appearing in the bucket
    fetch above. Without this, our local copy would stay stuck showing it
    as OPEN/PENDING forever, so it'd keep surfacing in Shift Watch even
    after it's actually done. Re-check every roster ticket we're still
    showing as OPEN/PENDING by id, mirroring the personal sync's
    supplemental pass - no need to keep re-checking ones already closed."""
    stale_ids = (
        await session.execute(select(Ticket.id).where(Ticket.is_tracked.is_(False), Ticket.status.in_(("OPEN", "PENDING"))))
    ).scalars().all()

    checked = updated = events = 0
    errors: list[str] = []
    for ticket_id in stale_ids:
        if ticket_id in touched_ids:
            continue
        checked += 1
        try:
            ingested = await refresh_ticket_snapshot(client, session, ticket_id, settings, now)
            if ingested:
                updated += 1
            events += ingested
            _apply_progress(run, base, checked, updated, events)
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            errors.append(f"ticket {ticket_id}: {exc}")

    return {"checked": checked, "updated": updated, "events": events, "errors": errors}


async def run_roster_sync(client: TrinityClient, session: AsyncSession, settings: Settings, run_id: int | None = None) -> dict:
    """run_id is optional so this can still be called directly (tests, ad-hoc
    scripts) without a SyncRun row - when given, it gets the same live
    progress + final status tracking as the personal sync's SyncRun."""
    run = await session.get(SyncRun, run_id) if run_id is not None else None
    if run is not None:
        # Rough denominator for a live percentage: currently-open/pending
        # roster tickets, since that's the same set both the bucket phase
        # (Trinity's buckets only ever list open tickets) and the
        # supplemental pass below actually touch - counting already-closed
        # roster tickets too would make this never reach 100%.
        run.total_estimate = (
            await session.execute(
                select(func.count())
                .select_from(Ticket)
                .where(Ticket.is_tracked.is_(False), Ticket.status.in_(("OPEN", "PENDING")))
            )
        ).scalar_one() or None
        await session.commit()

    unassigned_bucket = await get_value(session, "roster_bucket_unassigned_id", DEFAULT_ROSTER_BUCKET_UNASSIGNED_ID)
    assigned_bucket = await get_value(session, "roster_bucket_assigned_id", DEFAULT_ROSTER_BUCKET_ASSIGNED_ID)

    now = utcnow()
    touched_ids: set[str] = set()
    base = {"checked": 0, "updated": 0, "events": 0}
    results = []
    try:
        for bucket_id in (unassigned_bucket, assigned_bucket):
            if not bucket_id:
                continue
            result = await _sync_bucket(client, session, settings, bucket_id, now, touched_ids, run, base)
            results.append(result)
            base["checked"] += result["checked"]
            base["updated"] += result["updated"]
            base["events"] += result["events"]

        result = await _supplemental_pass(client, session, settings, now, touched_ids, run, base)
        results.append(result)

        if run is not None:
            errors = [e for r in results for e in r["errors"]]
            run.status = "success" if not errors else "partial_failure"
            run.error_summary = "; ".join(errors[:5]) if errors else None
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        if run is not None:
            run = await session.get(SyncRun, run_id)
            run.status = "error"
            run.error_summary = str(exc)

    summary = {
        "tickets_checked": sum(r["checked"] for r in results),
        "tickets_updated": sum(r["updated"] for r in results),
        "events_ingested": sum(r["events"] for r in results),
        "errors": [e for r in results for e in r["errors"]],
    }

    if run is not None:
        run.finished_at = utcnow()
        run.tickets_checked = summary["tickets_checked"]
        run.tickets_updated = summary["tickets_updated"]
        run.events_ingested = summary["events_ingested"]
        await session.commit()

    return summary

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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Ticket
from app.settings_store import DEFAULT_ROSTER_BUCKET_ASSIGNED_ID, DEFAULT_ROSTER_BUCKET_UNASSIGNED_ID, get_value
from app.sync.engine import ingest_ticket_for_roster, refresh_roster_ticket_incremental, refresh_ticket_snapshot
from app.sync.timeutil import parse_trinity_dt, utcnow
from app.trinity_client import TrinityClient

ROSTER_SYNC_PAGE_LIMIT = 100


async def _sync_bucket(
    client: TrinityClient, session: AsyncSession, settings: Settings, bucket_id: str, now: datetime, touched_ids: set[str]
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
                        continue
                    ingested = await refresh_roster_ticket_incremental(client, session, item, settings, now)
                updated += 1
                events += ingested
                await session.flush()
            except Exception as exc:  # noqa: BLE001
                # A flush failure leaves the session unable to run any
                # further statements until rolled back - without this, one
                # bad ticket would silently poison every ticket after it in
                # this same pass.
                await session.rollback()
                errors.append(f"ticket #{item.get('num')}: {exc}")

        cursor = page.get("next_cursor")
        if not cursor:
            break

    # Commit per bucket, not once at the end - holding one long transaction
    # across both buckets would block the personal sync / "Sync now" / any
    # other write for the whole duration.
    await session.commit()
    return {"checked": checked, "updated": updated, "events": events, "errors": errors}


async def _supplemental_pass(
    client: TrinityClient, session: AsyncSession, settings: Settings, now: datetime, touched_ids: set[str]
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
            await session.flush()
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            errors.append(f"ticket {ticket_id}: {exc}")

    await session.commit()
    return {"checked": checked, "updated": updated, "events": events, "errors": errors}


async def run_roster_sync(client: TrinityClient, session: AsyncSession, settings: Settings) -> dict:
    unassigned_bucket = await get_value(session, "roster_bucket_unassigned_id", DEFAULT_ROSTER_BUCKET_UNASSIGNED_ID)
    assigned_bucket = await get_value(session, "roster_bucket_assigned_id", DEFAULT_ROSTER_BUCKET_ASSIGNED_ID)

    now = utcnow()
    touched_ids: set[str] = set()
    results = [
        await _sync_bucket(client, session, settings, bucket_id, now, touched_ids)
        for bucket_id in (unassigned_bucket, assigned_bucket)
        if bucket_id
    ]
    results.append(await _supplemental_pass(client, session, settings, now, touched_ids))

    return {
        "tickets_checked": sum(r["checked"] for r in results),
        "tickets_updated": sum(r["updated"] for r in results),
        "events_ingested": sum(r["events"] for r in results),
        "errors": [e for r in results for e in r["errors"]],
    }

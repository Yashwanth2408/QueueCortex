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

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Ticket
from app.settings_store import DEFAULT_ROSTER_BUCKET_ASSIGNED_ID, DEFAULT_ROSTER_BUCKET_UNASSIGNED_ID, get_value
from app.sync.engine import ingest_ticket_for_roster, refresh_roster_ticket_incremental
from app.sync.timeutil import parse_trinity_dt, utcnow
from app.trinity_client import TrinityClient

ROSTER_SYNC_PAGE_LIMIT = 100


async def _sync_bucket(client: TrinityClient, session: AsyncSession, settings: Settings, bucket_id: str, now: datetime) -> dict:
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
                errors.append(f"ticket #{item.get('num')}: {exc}")

        cursor = page.get("next_cursor")
        if not cursor:
            break

    # Commit per bucket, not once at the end - holding one long transaction
    # across both buckets would block the personal sync / "Sync now" / any
    # other write for the whole duration.
    await session.commit()
    return {"checked": checked, "updated": updated, "events": events, "errors": errors}


async def run_roster_sync(client: TrinityClient, session: AsyncSession, settings: Settings) -> dict:
    unassigned_bucket = await get_value(session, "roster_bucket_unassigned_id", DEFAULT_ROSTER_BUCKET_UNASSIGNED_ID)
    assigned_bucket = await get_value(session, "roster_bucket_assigned_id", DEFAULT_ROSTER_BUCKET_ASSIGNED_ID)

    now = utcnow()
    results = [
        await _sync_bucket(client, session, settings, bucket_id, now)
        for bucket_id in (unassigned_bucket, assigned_bucket)
        if bucket_id
    ]

    return {
        "tickets_checked": sum(r["checked"] for r in results),
        "tickets_updated": sum(r["updated"] for r in results),
        "events_ingested": sum(r["events"] for r in results),
        "errors": [e for r in results for e in r["errors"]],
    }

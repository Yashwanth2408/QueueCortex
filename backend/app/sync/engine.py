"""The sync engine: pulls ticket state + full event history from Trinity into
the local database. `tickets` is a derived/cached current-state row;
`ticket_events` is the append-only source of truth; `status_transitions` has
one row per status-change EVENT (not per ticket) so that "closed yesterday,
reopened+reclosed today" attributes correctly to today with zero special
casing anywhere downstream.
"""

import json
import re
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import (
    Agent,
    AssignmentEvent,
    Customer,
    CsatEvent,
    LevelTransition,
    LocalNote,
    StatusTransition,
    SyncRun,
    SyncState,
    Tag,
    TagTypeMapping,
    Ticket,
    TicketDuplicate,
    TicketEvent,
    TicketTag,
)
from app.trinity_client import TrinityClient
from app.sync.timeutil import parse_trinity_dt, to_reporting_date, utcnow

DUPLICATE_RE = re.compile(r"duplicate\s+#?(\d+)", re.IGNORECASE)
CLOSED_STATUSES = ("CLOSED", "REJECTED")

# Sensible default label -> type seeding, applied the first time a tag is
# observed. The user can always repoint/rename/delete via Settings -> Tag
# Mapping afterwards; this just avoids an all-"Uncategorized" cold start.
DEFAULT_LABEL_TYPE_MAP: dict[str, tuple[str, int]] = {
    "deployment": ("Deployment", 10),
    "github": ("Deployment", 11),
    "billing": ("Billing", 20),
    "subscription-issue": ("Billing", 21),
    "refund": ("Refund", 30),
    "cancel-subscription": ("Refund", 31),
    "legal-compliance": ("Legal/Compliance", 40),
    "agent quality": ("Agent Quality", 50),
    "database": ("Technical", 60),
}


class TicketNotFoundError(Exception):
    def __init__(self, num: int):
        super().__init__(f"No ticket found with number {num}")
        self.num = num


class SyncAlreadyRunningError(Exception):
    pass


def _to_text(value):
    """Trinity audit events are usually str old_value/new_value, but some
    actions (e.g. custom-field changes) carry a structured {key, value} dict
    instead. Normalize anything non-str/None to a JSON string so it always
    fits the Text column."""
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value)


# ---------------------------------------------------------------------------
# Registry upserts (customers, tags, agents)
# ---------------------------------------------------------------------------

async def _upsert_customer(session: AsyncSession, customer: dict | None, now: datetime) -> str | None:
    if not customer or not customer.get("id"):
        return None
    row = await session.get(Customer, customer["id"])
    if row is None:
        row = Customer(id=customer["id"], first_seen_at=now, last_seen_at=now)
        session.add(row)
    row.email = customer.get("email")
    row.first_name = customer.get("first_name")
    row.last_name = customer.get("last_name")
    if customer.get("custom_fields"):
        row.custom_fields = customer["custom_fields"]
    row.last_seen_at = now
    return row.id


async def _upsert_tags(session: AsyncSession, ticket_id: str, tags: list[str], tag_ids: list[str], now: datetime) -> None:
    for tag_id, label in zip(tag_ids or [], tags or []):
        row = await session.get(Tag, tag_id)
        if row is None:
            row = Tag(tag_id=tag_id, label=label, first_seen_at=now, last_seen_at=now)
            session.add(row)
            default = DEFAULT_LABEL_TYPE_MAP.get(label.strip().lower())
            if default:
                type_label, priority = default
                session.add(TagTypeMapping(tag_id=tag_id, type_label=type_label, priority=priority, updated_at=now))
        else:
            row.label = label
            row.last_seen_at = now
    existing = (
        await session.execute(select(TicketTag).where(TicketTag.ticket_id == ticket_id))
    ).scalars().all()
    existing_ids = {r.tag_id for r in existing}
    wanted_ids = set(tag_ids or [])
    for r in existing:
        if r.tag_id not in wanted_ids:
            await session.delete(r)
    for tag_id in wanted_ids - existing_ids:
        session.add(TicketTag(ticket_id=ticket_id, tag_id=tag_id))


async def _upsert_agent_stub(session: AsyncSession, agent_id: str | None, email: str | None, now: datetime) -> None:
    if not agent_id:
        return
    row = await session.get(Agent, agent_id)
    if row is None:
        session.add(Agent(id=agent_id, email=email or "", synced_at=now))
    elif email:
        row.email = email


async def recompute_derived_type(session: AsyncSession, ticket: Ticket) -> None:
    tag_ids = ticket.tag_ids_cache or []
    if not tag_ids:
        ticket.derived_type = "Uncategorized"
        return
    mappings = (
        await session.execute(
            select(TagTypeMapping).where(TagTypeMapping.tag_id.in_(tag_ids)).order_by(TagTypeMapping.priority)
        )
    ).scalars().all()
    ticket.derived_type = mappings[0].type_label if mappings else "Uncategorized"


async def recompute_all_derived_types(session: AsyncSession) -> None:
    tickets = (await session.execute(select(Ticket))).scalars().all()
    for t in tickets:
        await recompute_derived_type(session, t)
    await session.commit()


# ---------------------------------------------------------------------------
# Ticket snapshot ingestion
# ---------------------------------------------------------------------------

async def _upsert_ticket_from_list_item(
    session: AsyncSession, item: dict, settings: Settings, now: datetime, mark_personal: bool = True
) -> Ticket:
    ticket = await session.get(Ticket, item["id"])
    is_new = ticket is None
    if is_new:
        ticket = Ticket(
            id=item["id"],
            num=item["num"],
            status=item["status"],
            created_at_trinity=parse_trinity_dt(item["created_at"]),
            updated_at_trinity=parse_trinity_dt(item["updated_at"]),
            last_event_at=parse_trinity_dt(item["updated_at"]),
            added_to_tracker_at=now,
            last_synced_at=now,
            # Explicit, not relying on the column default: a brand-new ticket
            # ingested via the roster path (mark_personal=False) must NOT
            # start out is_tracked=True just because that's the column's
            # declared default for the (far more common) personal-sync case.
            is_tracked=mark_personal,
        )
        session.add(ticket)

    customer = item.get("customer")
    customer_id = await _upsert_customer(session, customer, now)
    team = item.get("team") or {}
    await _upsert_agent_stub(session, item.get("assigned_agent_id"), item.get("assigned_to"), now)

    ticket.subject = item.get("subject")
    ticket.status = item["status"]
    ticket.level = item.get("level")
    ticket.channel = item.get("channel")
    ticket.team = team.get("name") if isinstance(team, dict) else team
    ticket.assigned_agent_id = item.get("assigned_agent_id")
    ticket.assigned_to_email = item.get("assigned_to")
    ticket.customer_id = customer_id
    ticket.tags_cache = item.get("tags") or []
    ticket.tag_ids_cache = item.get("tag_ids") or []
    ticket.last_customer_message_at = parse_trinity_dt(item.get("last_customer_message_at"))
    ticket.updated_at_trinity = parse_trinity_dt(item["updated_at"])
    ticket.trinity_url = settings.trinity_ticket_url_template.format(id=item["id"], num=item["num"])
    if mark_personal:
        # Only the tracked-agent sync path (run_full_backfill/run_incremental_sync)
        # sets this - it's the boundary that keeps Dashboard/Analytics scoped to
        # Yashwanth's own tickets even once Shift Watch starts ingesting other
        # agents' tickets into these same tables. Never flip it back to False:
        # a ticket taken from the tracked agent should stay in their history
        # (taken_from_me tracking) even if a roster agent now holds it.
        ticket.is_tracked = True
    ticket.last_synced_at = now
    ticket.sync_error = None

    await _upsert_tags(session, ticket.id, item.get("tags") or [], item.get("tag_ids") or [], now)
    await recompute_derived_type(session, ticket)
    return ticket


async def _enrich_ticket_from_get_ticket(session: AsyncSession, ticket: Ticket, full: dict, now: datetime) -> None:
    customer = full.get("customer")
    if customer:
        await _upsert_customer(session, customer, now)
    ticket.source = full.get("source")
    ticket.overwatch_status = full.get("overwatch_status")
    ticket.ticket_custom_fields = full.get("custom_fields")
    thread_stats = full.get("thread_stats") or {}
    ticket.thread_total_events = thread_stats.get("total_events")
    ticket.thread_messages = thread_stats.get("messages")
    ticket.thread_notes = thread_stats.get("notes")
    ticket.thread_system_events = thread_stats.get("system_events")
    last_event_at = parse_trinity_dt(thread_stats.get("last_event_at"))
    if last_event_at:
        ticket.last_event_at = last_event_at
    ticket.last_synced_at = now


# ---------------------------------------------------------------------------
# Event ingestion + derived rows
# ---------------------------------------------------------------------------

async def _insert_events(session: AsyncSession, ticket: Ticket, events: list[dict], settings: Settings, now: datetime) -> int:
    if not events:
        return 0
    ids = [e["id"] for e in events]
    existing_ids = set(
        (await session.execute(select(TicketEvent.id).where(TicketEvent.id.in_(ids)))).scalars().all()
    )
    inserted = 0
    for e in events:
        if e["id"] in existing_ids:
            continue
        created_at = parse_trinity_dt(e["created_at"])
        row = TicketEvent(
            id=e["id"],
            ticket_id=ticket.id,
            ticket_num=ticket.num,
            seq=e["seq"],
            type=e["type"],
            visibility=e.get("visibility"),
            direction=e.get("direction"),
            action=_to_text(e.get("action")),
            old_value=_to_text(e.get("old_value")),
            new_value=_to_text(e.get("new_value")),
            body=e.get("body"),
            author=_to_text(e.get("author")),
            author_email=_to_text(e.get("author_email")),
            attachments=e.get("attachments"),
            mentions=e.get("mentions"),
            event_metadata=e.get("metadata") or {},
            created_at=created_at,
            ingested_at=now,
        )
        session.add(row)
        # Flush before deriving dependent rows (assignment/status-transition/
        # csat events all FK-reference ticket_events.id) - now that SQLite
        # foreign_keys=ON is enforced, the parent row must actually be
        # inserted before a dependent row referencing it is flushed.
        await session.flush()
        await _derive_from_event(session, ticket, row, settings)
        inserted += 1
    return inserted


NEARBY_NOTE_WINDOW_MINUTES = 10


async def _find_nearby_internal_note(
    session: AsyncSession, ticket_id: str, author_email: str | None, around: datetime
) -> str | None:
    """Best-effort only: Trinity's level_changed/unassigned audit events carry
    no reason field of their own (confirmed against real synced data), so
    this looks for an internal note the same author posted shortly before
    the event - never asserted as fact, always shown to the user as a guess.
    Only looks backward in time (the natural sequence is explain-then-act,
    and this also avoids referencing a later event not yet inserted mid-batch
    during ingestion, since events are derived in the same order they're
    inserted)."""
    if not author_email:
        return None
    window_start = around - timedelta(minutes=NEARBY_NOTE_WINDOW_MINUTES)
    row = (
        await session.execute(
            select(TicketEvent)
            .where(
                TicketEvent.ticket_id == ticket_id,
                TicketEvent.type == "note",
                TicketEvent.visibility == "internal",
                TicketEvent.author_email == author_email,
                TicketEvent.created_at.between(window_start, around),
            )
            .order_by(TicketEvent.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return row.body if row else None


async def _derive_from_event(session: AsyncSession, ticket: Ticket, event: TicketEvent, settings: Settings) -> None:
    if event.type == "audit" and event.action == "status_changed":
        is_close = event.new_value in CLOSED_STATUSES
        is_reopen = event.old_value == "CLOSED" and event.new_value in ("OPEN", "PENDING")
        is_customer_reopen = bool((event.event_metadata or {}).get("reason") == "customer_reply")
        session.add(
            StatusTransition(
                ticket_id=ticket.id,
                ticket_num=ticket.num,
                event_id=event.id,
                seq=event.seq,
                old_status=event.old_value,
                new_status=event.new_value,
                is_close=is_close,
                is_reopen=is_reopen,
                is_customer_triggered_reopen=is_customer_reopen,
                event_date=to_reporting_date(event.created_at, settings.reporting_timezone),
                agent_email=event.author_email,
                created_at=event.created_at,
            )
        )
    elif event.type == "audit" and event.action in ("assigned", "unassigned"):
        old_assignee = event.old_value
        new_assignee = event.new_value
        meta = event.event_metadata or {}
        is_gain = new_assignee == settings.tracked_agent_email
        # "Taken from me" excludes the tracked agent voluntarily releasing
        # their own ticket (author_email == old_assignee == tracked agent) -
        # that's a deliberate hand-off, not something done TO them.
        is_taken = (
            old_assignee == settings.tracked_agent_email
            and (event.action == "unassigned" or new_assignee != settings.tracked_agent_email)
            and event.author_email != settings.tracked_agent_email
        )
        # The mirror image of is_taken: the tracked agent releasing their OWN
        # ticket themselves - previously just excluded from is_taken with no
        # positive record of its own; now tracked explicitly so it shows up
        # as "you unassigned yourself" rather than being invisible.
        is_self_release = (
            old_assignee == settings.tracked_agent_email
            and event.author_email == settings.tracked_agent_email
            and (event.action == "unassigned" or new_assignee != settings.tracked_agent_email)
        )
        # Trinity records the actor as whichever party's own action caused the
        # change (the agent giving it up, or the agent taking it) - it is
        # "System"/no email specifically when Trinity itself auto-unassigns
        # (e.g. reopened while the assignee is offline), which is exactly the
        # "system unassigned me" signal, distinct from a person taking it.
        is_system = event.author_email is None and (event.author is None or event.author == "System")
        reason = meta.get("reason")
        if is_self_release and not reason:
            reason = await _find_nearby_internal_note(session, ticket.id, event.author_email, event.created_at)
        session.add(
            AssignmentEvent(
                ticket_id=ticket.id,
                ticket_num=ticket.num,
                event_id=event.id,
                seq=event.seq,
                action=event.action,
                old_assignee=old_assignee,
                new_assignee=new_assignee,
                is_gain_for_tracked_agent=is_gain,
                is_taken_from_tracked_agent=is_taken,
                is_self_release_for_tracked_agent=is_self_release,
                is_system_action=is_system,
                reason=reason,
                performed_by_email=event.author_email,
                event_date=to_reporting_date(event.created_at, settings.reporting_timezone),
                created_at=event.created_at,
            )
        )
        if is_gain and (ticket.first_assigned_to_agent_at is None or event.created_at < ticket.first_assigned_to_agent_at):
            ticket.first_assigned_to_agent_at = event.created_at

    elif event.type == "audit" and event.action == "level_changed":
        # Only real transitions AWAY FROM L2 count - not the ticket's initial
        # level classification (old_value is None the first time Trinity
        # assigns a level at all, confirmed against real data: ~130 of these
        # exist and are not "de-escalations"), and not an L1/L3 ticket moving
        # INTO L2 (that's a gain, not something escalated/de-escalated away
        # from the tracked agent).
        is_escalation = event.old_value == "L2" and event.new_value == "L3"
        is_deescalation = event.old_value == "L2" and event.new_value == "L1"
        is_system = event.author_email is None and (event.author is None or event.author == "System")
        possible_reason = None
        if not is_system:
            possible_reason = await _find_nearby_internal_note(session, ticket.id, event.author_email, event.created_at)
        session.add(
            LevelTransition(
                ticket_id=ticket.id,
                ticket_num=ticket.num,
                event_id=event.id,
                seq=event.seq,
                old_level=event.old_value,
                new_level=event.new_value,
                is_escalation=is_escalation,
                is_deescalation=is_deescalation,
                is_system_action=is_system,
                performed_by_email=event.author_email,
                possible_reason=possible_reason,
                event_date=to_reporting_date(event.created_at, settings.reporting_timezone),
                created_at=event.created_at,
            )
        )

    elif event.type == "audit" and event.action in ("csat_sent", "csat_cancelled"):
        meta = event.event_metadata or {}
        session.add(
            CsatEvent(
                ticket_id=ticket.id,
                event_id=event.id,
                action=event.action,
                close_cycle_index=meta.get("close_cycle_index"),
                csat_survey_id=meta.get("csat_survey_id"),
                created_at=event.created_at,
            )
        )

    elif event.type == "note" and event.body:
        match = DUPLICATE_RE.search(event.body)
        if match:
            session.add(
                TicketDuplicate(
                    ticket_id=ticket.id,
                    duplicate_of_num=int(match.group(1)),
                    detected_from_event_id=event.id,
                    detected_at=event.created_at,
                )
            )


async def _sync_ticket_events(
    client: TrinityClient, session: AsyncSession, ticket: Ticket, settings: Settings, now: datetime, full: bool
) -> int:
    cursor = None
    max_seq_seen = ticket.last_seq
    events_ingested = 0
    page_limit = 200 if full else 100
    while True:
        page = await client.get_ticket_messages(ticket.id, cursor=cursor, limit=page_limit, include_internal=True)
        events = page.get("events", [])
        if events:
            page_max_seq = max(e["seq"] for e in events)
            page_min_seq = min(e["seq"] for e in events)
            max_seq_seen = max(max_seq_seen, page_max_seq)
            new_events = events if full else [e for e in events if e["seq"] > ticket.last_seq]
            events_ingested += await _insert_events(session, ticket, new_events, settings, now)
        else:
            page_min_seq = None
        next_cursor = page.get("next_cursor")
        has_more = page.get("has_more") if page.get("has_more") is not None else bool(next_cursor)
        if not has_more or not next_cursor:
            break
        if not full and page_min_seq is not None and page_min_seq <= ticket.last_seq:
            break
        cursor = next_cursor
    ticket.last_seq = max(ticket.last_seq, max_seq_seen)
    return events_ingested


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

FALLBACK_SCAN_MAX_PAGES = 25
FALLBACK_SCAN_PAGE_SIZE = 200


async def resolve_ticket_num(session: AsyncSession, client: TrinityClient, num: int) -> str:
    existing = (await session.execute(select(Ticket).where(Ticket.num == num))).scalar_one_or_none()
    if existing:
        return existing.id

    # Fast path: Trinity's free-text `query` search sometimes resolves an
    # exact ticket number directly - but only reliably for very recently
    # created tickets. Confirmed against production data: for anything
    # outside that recency window it silently falls back to returning
    # unrelated "recent" tickets instead of an empty result, so a defensive
    # exact-match check here is required (not just "any items returned").
    result = await client.list_tickets(query=str(num), limit=5)
    items = result.get("items", [])
    match = next((it for it in items if it.get("num") == num), None)
    if match:
        return match["id"]

    # Fallback: ticket numbers are assigned sequentially by creation order
    # system-wide (confirmed: paginating by created_at desc yields a dense,
    # monotonically decreasing `num` sequence). Page through newest-first
    # until we pass the target number or find it.
    cursor = None
    for _ in range(FALLBACK_SCAN_MAX_PAGES):
        page = await client.list_tickets(sort_key="created_at", sort_dir="desc", limit=FALLBACK_SCAN_PAGE_SIZE, cursor=cursor)
        page_items = page.get("items", [])
        if not page_items:
            break
        match = next((it for it in page_items if it.get("num") == num), None)
        if match:
            return match["id"]
        if min(it["num"] for it in page_items) < num:
            break
        cursor = page.get("next_cursor")
        if not cursor:
            break

    raise TicketNotFoundError(num)


async def _ingest_single_ticket(
    client: TrinityClient,
    session: AsyncSession,
    ticket_id: str,
    settings: Settings,
    now: datetime,
    full: bool,
    mark_personal: bool = True,
) -> tuple[Ticket, int]:
    if full:
        full_data = await client.get_ticket(ticket_id)
        item = {
            "id": full_data["id"],
            "num": full_data["num"],
            "subject": full_data.get("subject"),
            "status": full_data["status"],
            "level": full_data.get("level"),
            "channel": full_data.get("channel"),
            "team": full_data.get("team"),
            "assigned_agent_id": full_data.get("assigned_agent_id"),
            "assigned_to": full_data.get("assigned_to"),
            "customer": full_data.get("customer"),
            "tags": full_data.get("tags"),
            "tag_ids": full_data.get("tag_ids"),
            "last_customer_message_at": full_data.get("last_customer_message_at"),
            "created_at": full_data["created_at"],
            "updated_at": full_data["updated_at"],
        }
        ticket = await _upsert_ticket_from_list_item(session, item, settings, now, mark_personal=mark_personal)
        await _enrich_ticket_from_get_ticket(session, ticket, full_data, now)
    else:
        ticket = await session.get(Ticket, ticket_id)
        full_data = await client.get_ticket(ticket_id)
        await _enrich_ticket_from_get_ticket(session, ticket, full_data, now)
        if mark_personal:
            # Covers claiming a ticket Shift Watch already pulled in (is_tracked=False,
            # since it was ingested for a different agent) via "add ticket by number" -
            # the explicit personal add must bring it into the tracked-agent's scope.
            ticket.is_tracked = True

    events_ingested = await _sync_ticket_events(client, session, ticket, settings, now, full=full)
    await recompute_derived_type(session, ticket)
    await session.flush()
    return ticket, events_ingested


async def ingest_ticket_for_roster(
    client: TrinityClient, session: AsyncSession, ticket_id: str, settings: Settings, now: datetime, full: bool
) -> tuple[Ticket, int]:
    """Entry point for the roster (Shift Watch) sync path - identical
    ingestion pipeline to the tracked-agent sync, but never marks the
    ticket personal (`is_tracked`), keeping Yashwanth's own Dashboard/
    Analytics numbers unaffected by other agents' tickets."""
    return await _ingest_single_ticket(client, session, ticket_id, settings, now, full=full, mark_personal=False)


async def refresh_roster_ticket_incremental(
    client: TrinityClient, session: AsyncSession, item: dict, settings: Settings, now: datetime
) -> int:
    """Lightweight incremental refresh for a roster ticket already ingested
    at least once - mirrors run_incremental_sync's non-full branch exactly,
    still never marking it personal (`mark_personal=False`)."""
    ticket = await _upsert_ticket_from_list_item(session, item, settings, now, mark_personal=False)
    full_data = await client.get_ticket(ticket.id)
    await _enrich_ticket_from_get_ticket(session, ticket, full_data, now)
    ingested = await _sync_ticket_events(client, session, ticket, settings, now, full=False)
    await recompute_derived_type(session, ticket)
    return ingested


async def refresh_ticket_snapshot(
    client: TrinityClient, session: AsyncSession, ticket_id: str, settings: Settings, now: datetime
) -> int:
    """Re-fetch a single already-known ticket by id and pull any new events
    since last sync. Used by supplemental passes that re-check tickets
    directly by id: Trinity's filtered `list_tickets` calls (assigned_to=...,
    bucket_id=...) only return CURRENT matches, so a ticket that quietly
    changes status/assignment and drops out of that filter (e.g. closes, or
    gets reassigned away) would otherwise never be seen again and the local
    copy would go stale forever."""
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        return 0
    full_data = await client.get_ticket(ticket_id)
    # Stub the agent record first if this is someone we've never seen
    # before (e.g. a roster ticket reassigned to a brand-new agent) -
    # assigned_agent_id is FK-constrained against agents.id.
    await _upsert_agent_stub(session, full_data.get("assigned_agent_id"), full_data.get("assigned_to"), now)
    ticket.status = full_data["status"]
    ticket.level = full_data.get("level")
    ticket.assigned_agent_id = full_data.get("assigned_agent_id")
    ticket.assigned_to_email = full_data.get("assigned_to")
    if full_data.get("tags") is not None:
        ticket.tags_cache = full_data.get("tags")
        ticket.tag_ids_cache = full_data.get("tag_ids")
        await _upsert_tags(session, ticket.id, full_data.get("tags") or [], full_data.get("tag_ids") or [], now)
    await _enrich_ticket_from_get_ticket(session, ticket, full_data, now)
    ingested = await _sync_ticket_events(client, session, ticket, settings, now, full=False)
    await recompute_derived_type(session, ticket)
    return ingested


async def create_pending_run(session: AsyncSession, run_type: str) -> int:
    run = SyncRun(run_type=run_type, started_at=utcnow(), status="running")
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run.id


async def run_full_backfill(client: TrinityClient, session: AsyncSession, settings: Settings, run_id: int) -> SyncRun:
    now = utcnow()
    run = await session.get(SyncRun, run_id)

    # Trinity's list_tickets never reports a total, so the only cheap way to
    # get a real denominator for a live percentage is ticket_counts, which
    # covers every status (a full backfill has no status filter either).
    try:
        counts = await client.ticket_counts(assigned_to=settings.tracked_agent_email)
        run.total_estimate = sum(v for v in counts.values() if isinstance(v, int))
    except Exception:  # noqa: BLE001
        run.total_estimate = None
    await session.commit()

    checked = updated = events = 0
    try:
        cursor = None
        while True:
            page = await client.list_tickets(
                assigned_to=settings.tracked_agent_email, sort_key="updated_at", sort_dir="desc", limit=100, cursor=cursor
            )
            items = page.get("items", [])
            for item in items:
                _, ingested = await _ingest_single_ticket(client, session, item["id"], settings, now, full=True)
                checked += 1
                updated += 1
                events += ingested
                run.tickets_checked = checked
                run.tickets_updated = updated
                run.events_ingested = events
                await session.commit()
            cursor = page.get("next_cursor")
            if not cursor:
                break
        run.status = "success"
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        run = await session.get(SyncRun, run_id)
        run.status = "error"
        run.error_summary = str(exc)

    run.finished_at = utcnow()
    run.tickets_checked = checked
    run.tickets_updated = updated
    run.events_ingested = events

    state = await session.get(SyncState, "primary")
    if state is None:
        state = SyncState(scope="primary")
        session.add(state)
    state.last_full_backfill_at = run.finished_at
    await session.commit()
    return run


async def run_incremental_sync(client: TrinityClient, session: AsyncSession, settings: Settings, run_id: int) -> SyncRun:
    now = utcnow()
    run = await session.get(SyncRun, run_id)

    # Rough denominator for a live percentage: the supplemental pass below
    # (usually the slower half, since it re-checks every tracked ticket by
    # id) scales with exactly this count, and phase one's checked/updated
    # tally converges toward it too by the time the whole run finishes -
    # good enough for "roughly how far along", not an exact count.
    run.total_estimate = (
        await session.execute(select(func.count()).select_from(Ticket).where(Ticket.is_tracked.is_(True)))
    ).scalar_one() or None
    await session.commit()

    checked = updated = events = 0
    touched_ids: set[str] = set()
    try:
        cursor = None
        stop = False
        while not stop:
            page = await client.list_tickets(
                assigned_to=settings.tracked_agent_email, sort_key="updated_at", sort_dir="desc", limit=50, cursor=cursor
            )
            items = page.get("items", [])
            if not items:
                break
            for item in items:
                checked += 1
                touched_ids.add(item["id"])
                existing = await session.get(Ticket, item["id"])
                remote_updated = parse_trinity_dt(item["updated_at"])
                if existing is not None and existing.updated_at_trinity is not None and remote_updated <= existing.updated_at_trinity:
                    stop = True
                    break
                if existing is None:
                    _, ingested = await _ingest_single_ticket(client, session, item["id"], settings, now, full=True)
                else:
                    ticket = await _upsert_ticket_from_list_item(session, item, settings, now)
                    full_data = await client.get_ticket(ticket.id)
                    await _enrich_ticket_from_get_ticket(session, ticket, full_data, now)
                    ingested = await _sync_ticket_events(client, session, ticket, settings, now, full=False)
                    await recompute_derived_type(session, ticket)
                updated += 1
                events += ingested
                run.tickets_checked = checked
                run.tickets_updated = updated
                run.events_ingested = events
                await session.commit()
            cursor = page.get("next_cursor")
            if not cursor:
                break

        # Supplemental pass: Trinity's assigned_to filter only returns tickets
        # CURRENTLY assigned to the tracked agent. A ticket taken away (by a
        # person or by Trinity auto-unassigning an offline agent on reopen)
        # drops out of that list immediately - without this, we'd stop seeing
        # it and lose the "taken from me" event. Once a ticket is tracked, we
        # keep polling it directly by id regardless of current assignment.
        all_local_ids = (await session.execute(select(Ticket.id).where(Ticket.is_tracked.is_(True)))).scalars().all()
        for ticket_id in all_local_ids:
            if ticket_id in touched_ids:
                continue
            checked += 1
            ingested = await refresh_ticket_snapshot(client, session, ticket_id, settings, now)
            if ingested:
                updated += 1
            events += ingested
            run.tickets_checked = checked
            run.tickets_updated = updated
            run.events_ingested = events
            await session.commit()

        run.status = "success"
    except Exception as exc:  # noqa: BLE001
        # A failed commit above leaves the session unusable until rolled
        # back, which also expires `run` - re-fetch it before touching it
        # again (the local checked/updated/events counters are plain ints,
        # unaffected by the rollback).
        await session.rollback()
        run = await session.get(SyncRun, run_id)
        run.status = "error"
        run.error_summary = str(exc)

    run.finished_at = utcnow()
    run.tickets_checked = checked
    run.tickets_updated = updated
    run.events_ingested = events

    state = await session.get(SyncState, "primary")
    if state is None:
        state = SyncState(scope="primary")
        session.add(state)
    state.last_incremental_sync_at = run.finished_at
    state.last_incremental_sync_status = run.status
    state.last_incremental_sync_error = run.error_summary
    await session.commit()
    return run


async def add_ticket_by_number(client: TrinityClient, session: AsyncSession, settings: Settings, num: int) -> Ticket:
    now = utcnow()
    run = SyncRun(run_type="add_ticket", started_at=now, status="running")
    session.add(run)
    await session.flush()
    try:
        ticket_id = await resolve_ticket_num(session, client, num)
        existing = await session.get(Ticket, ticket_id)
        ticket, ingested = await _ingest_single_ticket(client, session, ticket_id, settings, now, full=existing is None)
        run.status = "success"
        run.tickets_checked = run.tickets_updated = 1
        run.events_ingested = ingested
    except Exception as exc:  # noqa: BLE001
        run.status = "error"
        run.error_summary = str(exc)
        run.finished_at = utcnow()
        await session.commit()
        raise
    run.finished_at = utcnow()
    await session.commit()
    return ticket


async def backfill_assignment_events(session: AsyncSession, settings: Settings) -> int:
    """One-off migration helper: derive assignment_events for
    assigned/unassigned audit events that were already ingested into
    ticket_events before this feature existed."""
    rows = (
        await session.execute(select(TicketEvent).where(TicketEvent.action.in_(("assigned", "unassigned"))))
    ).scalars().all()
    existing_event_ids = set((await session.execute(select(AssignmentEvent.event_id))).scalars().all())
    created = 0
    for event in rows:
        if event.id in existing_event_ids:
            continue
        ticket = await session.get(Ticket, event.ticket_id)
        if ticket is None:
            continue
        await _derive_from_event(session, ticket, event, settings)
        created += 1
    await session.commit()
    return created


async def backfill_level_events(session: AsyncSession, settings: Settings) -> int:
    """One-off migration helper: derive level_transitions for level_changed
    audit events that were already ingested into ticket_events before this
    feature existed."""
    rows = (await session.execute(select(TicketEvent).where(TicketEvent.action == "level_changed"))).scalars().all()
    existing_event_ids = set((await session.execute(select(LevelTransition.event_id))).scalars().all())
    created = 0
    for event in rows:
        if event.id in existing_event_ids:
            continue
        ticket = await session.get(Ticket, event.ticket_id)
        if ticket is None:
            continue
        await _derive_from_event(session, ticket, event, settings)
        created += 1
    await session.commit()
    return created


async def backfill_self_release_flags(session: AsyncSession, settings: Settings) -> int:
    """One-off migration helper: is_self_release_for_tracked_agent didn't
    exist before this feature - backfill it on already-derived
    assignment_events rows using the same condition as _derive_from_event,
    from data already stored (can't just re-derive, that would duplicate
    the existing rows)."""
    rows = (
        await session.execute(
            select(AssignmentEvent).where(
                AssignmentEvent.old_assignee == settings.tracked_agent_email,
                AssignmentEvent.is_self_release_for_tracked_agent.is_(False),
            )
        )
    ).scalars().all()
    updated = 0
    for r in rows:
        is_self_release = r.performed_by_email == settings.tracked_agent_email and (
            r.action == "unassigned" or r.new_assignee != settings.tracked_agent_email
        )
        if not is_self_release:
            continue
        r.is_self_release_for_tracked_agent = True
        if not r.reason:
            r.reason = await _find_nearby_internal_note(session, r.ticket_id, r.performed_by_email, r.created_at)
        updated += 1
    await session.commit()
    return updated


async def get_last_own_internal_note(session: AsyncSession, ticket_id: str, agent_email: str) -> str | None:
    row = (
        await session.execute(
            select(TicketEvent)
            .where(
                TicketEvent.ticket_id == ticket_id,
                TicketEvent.type == "note",
                TicketEvent.visibility == "internal",
                TicketEvent.author_email == agent_email,
            )
            .order_by(TicketEvent.seq.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return row.body if row else None

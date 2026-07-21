"""Shared derivation helpers used by both the ticket-list/detail endpoints
and analytics: reopen counts, last close/reopen timestamps, and the
"needs attention" smart-queue definition. All computed from `status_transitions`
/`ticket_events` (never from Trinity fields Trinity doesn't actually have,
e.g. there is no SLA/priority field — the aging check below is an explicit
local heuristic)."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import AssignmentEvent, StatusTransition, Ticket, TicketEvent
from app.settings_store import get_value
from app.sync.timeutil import to_reporting_date, utcnow


async def compute_ticket_flags(session: AsyncSession, ticket_ids: list[str]) -> dict[str, dict]:
    if not ticket_ids:
        return {}
    rows = (
        await session.execute(
            select(StatusTransition).where(StatusTransition.ticket_id.in_(ticket_ids)).order_by(StatusTransition.seq)
        )
    ).scalars().all()
    out: dict[str, dict] = {tid: {"reopen_count": 0, "last_close_at": None, "last_reopen_at": None} for tid in ticket_ids}
    for r in rows:
        entry = out[r.ticket_id]
        if r.is_reopen:
            entry["reopen_count"] += 1
            entry["last_reopen_at"] = r.created_at
        if r.is_close:
            entry["last_close_at"] = r.created_at
    return out


async def compute_assignment_flags(session: AsyncSession, ticket_ids: list[str]) -> dict[str, dict]:
    """'Taken from me' = an assignment_events row where the tracked agent lost
    the ticket to something other than their own action - either Trinity
    auto-unassigning them (is_system_action) or another person taking/being
    given the ticket. Self-releases are excluded at derivation time."""
    if not ticket_ids:
        return {}
    rows = (
        await session.execute(
            select(AssignmentEvent)
            .where(AssignmentEvent.ticket_id.in_(ticket_ids), AssignmentEvent.is_taken_from_tracked_agent.is_(True))
            .order_by(AssignmentEvent.seq)
        )
    ).scalars().all()
    out: dict[str, dict] = {
        tid: {"taken_from_me_count": 0, "last_taken_from_me_at": None, "last_taken_from_me_reason": None} for tid in ticket_ids
    }
    for r in rows:
        entry = out[r.ticket_id]
        entry["taken_from_me_count"] += 1
        entry["last_taken_from_me_at"] = r.created_at
        if r.is_system_action:
            entry["last_taken_from_me_reason"] = "system_offline_unassign" if r.reason == "reopen_offline_assignee" else "system"
        elif r.new_assignee:
            entry["last_taken_from_me_reason"] = f"reassigned to {r.new_assignee}"
        else:
            entry["last_taken_from_me_reason"] = f"unassigned by {r.performed_by_email or 'someone'}"
    return out


class ClosedTodayEntry:
    __slots__ = ("ticket_id", "last_close_date", "total_close_count")

    def __init__(self, ticket_id: str, last_close_date, total_close_count: int):
        self.ticket_id = ticket_id
        self.last_close_date = last_close_date
        self.total_close_count = total_close_count


async def _actually_closed_entries(session: AsyncSession, settings: Settings) -> list[ClosedTodayEntry]:
    """Tickets genuinely sitting in CLOSED/REJECTED *right now* - not a raw
    "a close event happened at some point" count. A ticket that closed and
    then reopened again (same day or since) is correctly excluded: it isn't
    actually resolved, so counting it as closed would overstate progress."""
    closed_ticket_ids = (
        await session.execute(select(Ticket.id).where(Ticket.status.in_(("CLOSED", "REJECTED"))))
    ).scalars().all()
    if not closed_ticket_ids:
        return []

    rows = (
        await session.execute(
            select(StatusTransition)
            .where(StatusTransition.ticket_id.in_(closed_ticket_ids), StatusTransition.is_close.is_(True))
            .order_by(StatusTransition.ticket_id, StatusTransition.seq)
        )
    ).scalars().all()
    last_close_date: dict[str, object] = {}
    close_count: dict[str, int] = {}
    for r in rows:
        last_close_date[r.ticket_id] = r.event_date  # rows ordered by seq asc, so last write wins
        close_count[r.ticket_id] = close_count.get(r.ticket_id, 0) + 1

    return [ClosedTodayEntry(tid, last_close_date[tid], close_count[tid]) for tid in last_close_date]


async def compute_actually_closed_today_ids(session: AsyncSession, settings: Settings) -> set[str]:
    today = to_reporting_date(utcnow(), settings.reporting_timezone)
    entries = await _actually_closed_entries(session, settings)
    return {e.ticket_id for e in entries if e.last_close_date == today}


async def compute_today_snapshot(session: AsyncSession, settings: Settings) -> dict:
    now = utcnow()
    today = to_reporting_date(now, settings.reporting_timezone)

    entries = await _actually_closed_entries(session, settings)
    closed_today_entries = [e for e in entries if e.last_close_date == today]
    fresh_closed_today = sum(1 for e in closed_today_entries if e.total_close_count == 1)
    reclosed_today = len(closed_today_entries) - fresh_closed_today

    reopen_rows = (
        await session.execute(select(StatusTransition).where(StatusTransition.is_reopen.is_(True), StatusTransition.event_date == today))
    ).scalars().all()
    reopened_today = len(reopen_rows)
    customer_reopened_today = sum(1 for r in reopen_rows if r.is_customer_triggered_reopen)

    return {
        "closed_today": len(closed_today_entries),
        "fresh_closed_today": fresh_closed_today,
        "reclosed_today": reclosed_today,
        "reopened_today": reopened_today,
        "customer_reopened_today": customer_reopened_today,
    }


async def _latest_message_directions(session: AsyncSession, ticket_ids: list[str]) -> dict[str, str | None]:
    if not ticket_ids:
        return {}
    rows = (
        await session.execute(
            select(TicketEvent.ticket_id, TicketEvent.direction, TicketEvent.seq)
            .where(TicketEvent.ticket_id.in_(ticket_ids), TicketEvent.type == "message")
            .order_by(TicketEvent.ticket_id, TicketEvent.seq.desc())
        )
    ).all()
    latest: dict[str, str | None] = {}
    for ticket_id, direction, _seq in rows:
        if ticket_id not in latest:
            latest[ticket_id] = direction
    return latest


async def compute_needs_attention_ids(session: AsyncSession, settings: Settings) -> set[str]:
    open_tickets = (
        await session.execute(select(Ticket).where(Ticket.status.in_(("OPEN", "PENDING"))))
    ).scalars().all()
    if not open_tickets:
        return set()

    ids = [t.id for t in open_tickets]
    directions = await _latest_message_directions(session, ids)

    sla_thresholds: dict = await get_value(session, "sla_thresholds_json", {"OPEN": 24, "PENDING": 48})
    now = utcnow()
    today = to_reporting_date(now, settings.reporting_timezone)

    reopened_today_ids = set(
        (
            await session.execute(
                select(StatusTransition.ticket_id).where(
                    StatusTransition.ticket_id.in_(ids),
                    StatusTransition.is_reopen.is_(True),
                    StatusTransition.event_date == today,
                )
            )
        )
        .scalars()
        .all()
    )

    result = set()
    for t in open_tickets:
        if directions.get(t.id) == "inbound":
            result.add(t.id)
            continue
        if t.id in reopened_today_ids:
            result.add(t.id)
            continue
        threshold_hours = sla_thresholds.get(t.status)
        if threshold_hours is not None and (now - t.last_event_at) > timedelta(hours=threshold_hours):
            result.add(t.id)
    return result

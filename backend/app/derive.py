"""Shared derivation helpers used by both the ticket-list/detail endpoints
and analytics: reopen counts, last close/reopen timestamps, and the
"needs attention" smart-queue definition. All computed from `status_transitions`
/`ticket_events` (never from Trinity fields Trinity doesn't actually have,
e.g. there is no SLA/priority field — the aging check below is an explicit
local heuristic)."""

from collections import defaultdict
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


async def actually_closed_entries(session: AsyncSession, settings: Settings) -> list[ClosedTodayEntry]:
    """Tickets genuinely sitting in CLOSED/REJECTED *right now* - not a raw
    "a close event happened at some point" count. A ticket that closed and
    then reopened again (same day or since) is correctly excluded: it isn't
    actually resolved, so counting it as closed would overstate progress."""
    closed_ticket_ids = (
        await session.execute(
            select(Ticket.id).where(Ticket.status.in_(("CLOSED", "REJECTED")), Ticket.is_tracked.is_(True))
        )
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
    entries = await actually_closed_entries(session, settings)
    return {e.ticket_id for e in entries if e.last_close_date == today}


async def compute_today_snapshot(session: AsyncSession, settings: Settings) -> dict:
    now = utcnow()
    today = to_reporting_date(now, settings.reporting_timezone)

    entries = await actually_closed_entries(session, settings)
    closed_today_entries = [e for e in entries if e.last_close_date == today]
    fresh_closed_today = sum(1 for e in closed_today_entries if e.total_close_count == 1)
    reclosed_today = len(closed_today_entries) - fresh_closed_today

    reopen_rows = (
        await session.execute(
            select(StatusTransition)
            .join(Ticket, Ticket.id == StatusTransition.ticket_id)
            .where(StatusTransition.is_reopen.is_(True), StatusTransition.event_date == today, Ticket.is_tracked.is_(True))
        )
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


async def last_assignment_at_for_agent(session: AsyncSession, ticket_ids: list[str], agent_email: str) -> dict[str, datetime]:
    """Shift Watch's "held since": the most recent time each ticket was
    assigned to an arbitrary (roster) agent - not the tracked agent, so this
    queries the raw `new_assignee` column directly rather than the
    tracked-agent-only `is_gain_for_tracked_agent` flag. "Most recent", not
    "first ever", since a ticket can bounce away and come back."""
    if not ticket_ids:
        return {}
    rows = (
        await session.execute(
            select(AssignmentEvent)
            .where(AssignmentEvent.ticket_id.in_(ticket_ids), AssignmentEvent.new_assignee == agent_email)
            .order_by(AssignmentEvent.ticket_id, AssignmentEvent.seq)
        )
    ).scalars().all()
    last_assign_at: dict[str, datetime] = {}
    for r in rows:
        last_assign_at[r.ticket_id] = r.created_at  # ascending seq order - last write wins - most recent
    return last_assign_at


async def _first_self_assignments(session: AsyncSession, ticket_ids: list[str] | None = None) -> dict[str, datetime]:
    if ticket_ids is not None and not ticket_ids:
        return {}
    stmt = select(AssignmentEvent).where(AssignmentEvent.is_gain_for_tracked_agent.is_(True))
    if ticket_ids is not None:
        stmt = stmt.where(AssignmentEvent.ticket_id.in_(ticket_ids))
    rows = (await session.execute(stmt.order_by(AssignmentEvent.ticket_id, AssignmentEvent.seq))).scalars().all()
    first_assign_at: dict[str, datetime] = {}
    for r in rows:
        if r.ticket_id not in first_assign_at:
            first_assign_at[r.ticket_id] = r.created_at
    return first_assign_at


async def compute_response_durations(session: AsyncSession, settings: Settings) -> list[dict]:
    """One entry per ticket the tracked agent has ever taken ownership of and
    has since replied on: minutes between the first self-assignment and the
    first message the tracked agent sent afterwards, attributed to the day
    the reply itself went out (not the day the ticket was assigned)."""
    first_assign_at = await _first_self_assignments(session)
    if not first_assign_at:
        return []

    msg_rows = (
        await session.execute(
            select(TicketEvent)
            .where(
                TicketEvent.ticket_id.in_(list(first_assign_at.keys())),
                TicketEvent.type == "message",
                TicketEvent.author_email == settings.tracked_agent_email,
            )
            .order_by(TicketEvent.ticket_id, TicketEvent.seq)
        )
    ).scalars().all()

    out = []
    seen: set[str] = set()
    for r in msg_rows:
        if r.ticket_id in seen:
            continue
        assign_at = first_assign_at.get(r.ticket_id)
        if assign_at is None or r.created_at <= assign_at:
            continue
        seen.add(r.ticket_id)
        minutes = (r.created_at - assign_at).total_seconds() / 60
        out.append({"ticket_id": r.ticket_id, "date": to_reporting_date(r.created_at, settings.reporting_timezone), "minutes": minutes})
    return out


async def compute_final_close_durations(session: AsyncSession, settings: Settings) -> list[dict]:
    """One entry per ticket currently sitting CLOSED/REJECTED: minutes from
    ownership start to the close that stuck. If the ticket was ever reopened,
    the clock resets at the most recent reopen (not the original assignment) -
    this measures how long the final resolution leg actually took, not the
    ticket's total lifetime including reopen dwell time outside the agent's
    control."""
    entries = await actually_closed_entries(session, settings)
    if not entries:
        return []
    ticket_ids = [e.ticket_id for e in entries]

    st_rows = (
        await session.execute(
            select(StatusTransition).where(StatusTransition.ticket_id.in_(ticket_ids)).order_by(StatusTransition.ticket_id, StatusTransition.seq)
        )
    ).scalars().all()
    by_ticket: dict[str, list[StatusTransition]] = defaultdict(list)
    for r in st_rows:
        by_ticket[r.ticket_id].append(r)

    first_assign_at = await _first_self_assignments(session, ticket_ids)

    out = []
    for e in entries:
        transitions = by_ticket.get(e.ticket_id, [])
        close_rows = [t for t in transitions if t.is_close]
        if not close_rows:
            continue
        final_close = close_rows[-1]
        reopen_rows_before = [t for t in transitions if t.is_reopen and t.seq < final_close.seq]
        start_at = reopen_rows_before[-1].created_at if reopen_rows_before else first_assign_at.get(e.ticket_id)
        if start_at is None or final_close.created_at < start_at:
            continue
        minutes = (final_close.created_at - start_at).total_seconds() / 60
        out.append({"ticket_id": e.ticket_id, "date": final_close.event_date, "minutes": minutes})
    return out


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
        await session.execute(select(Ticket).where(Ticket.status.in_(("OPEN", "PENDING")), Ticket.is_tracked.is_(True)))
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

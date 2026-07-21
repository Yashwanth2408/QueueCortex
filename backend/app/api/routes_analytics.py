"""Analytics rollups. Everything here is built from `status_transitions`
(one row per status-change EVENT, not per ticket) so the "closed yesterday,
reclosed today counts toward today" rule falls out automatically: each close
event is bucketed by its own `event_date`, never the ticket's creation or
first-close date."""

from collections import defaultdict
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import StatusTransition, Ticket
from app.schemas import AnalyticsSummaryBucket, TimeseriesPoint

router = APIRouter(tags=["analytics"])


def _bucket_key(d: date, period: str) -> str:
    if period == "day":
        return d.isoformat()
    if period == "month":
        return f"{d.year:04d}-{d.month:02d}"
    return f"{d.year:04d}"


async def _load_close_and_reopen_events(session: AsyncSession, date_from: date | None, date_to: date | None):
    stmt = select(StatusTransition).order_by(StatusTransition.ticket_id, StatusTransition.seq)
    rows = (await session.execute(stmt)).scalars().all()

    tickets = {t.id: t for t in (await session.execute(select(Ticket))).scalars().all()}

    by_ticket: dict[str, list[StatusTransition]] = defaultdict(list)
    for r in rows:
        by_ticket[r.ticket_id].append(r)

    close_events = []
    reopen_events = []
    for ticket_id, transitions in by_ticket.items():
        ticket = tickets.get(ticket_id)
        if ticket is None:
            continue
        close_idx = 0
        close_rows = [t for t in transitions if t.is_close]
        for i, t in enumerate(close_rows):
            close_idx += 1
            close_events.append(
                {
                    "ticket_id": ticket_id,
                    "created_at": t.created_at,
                    "event_date": t.event_date,
                    "is_first_close": close_idx == 1,
                    "is_last_close_overall": i == len(close_rows) - 1,
                    "ticket_created_at": ticket.created_at_trinity,
                }
            )
        for t in transitions:
            if t.is_reopen:
                reopen_events.append(
                    {
                        "ticket_id": ticket_id,
                        "event_date": t.event_date,
                        "is_customer_triggered": t.is_customer_triggered_reopen,
                    }
                )

    if date_from:
        close_events = [e for e in close_events if e["event_date"] >= date_from]
        reopen_events = [e for e in reopen_events if e["event_date"] >= date_from]
    if date_to:
        close_events = [e for e in close_events if e["event_date"] <= date_to]
        reopen_events = [e for e in reopen_events if e["event_date"] <= date_to]

    return close_events, reopen_events


@router.get("/analytics/summary", response_model=list[AnalyticsSummaryBucket])
async def analytics_summary(
    period: str = Query("day", pattern="^(day|month|year)$"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
):
    close_events, reopen_events = await _load_close_and_reopen_events(session, date_from, date_to)

    buckets: dict[str, dict] = defaultdict(
        lambda: {
            "closed_count": 0,
            "fresh_close_count": 0,
            "reclose_count": 0,
            "reopened_count": 0,
            "customer_reopened_count": 0,
            "first_close_minutes": [],
            "final_close_minutes": [],
        }
    )

    for e in close_events:
        key = _bucket_key(e["event_date"], period)
        b = buckets[key]
        b["closed_count"] += 1
        minutes = (e["created_at"] - e["ticket_created_at"]).total_seconds() / 60
        if e["is_first_close"]:
            b["fresh_close_count"] += 1
            b["first_close_minutes"].append(minutes)
        else:
            b["reclose_count"] += 1
        if e["is_last_close_overall"]:
            b["final_close_minutes"].append(minutes)

    for e in reopen_events:
        key = _bucket_key(e["event_date"], period)
        b = buckets[key]
        b["reopened_count"] += 1
        if e["is_customer_triggered"]:
            b["customer_reopened_count"] += 1

    out = []
    for key in sorted(buckets.keys()):
        b = buckets[key]
        out.append(
            AnalyticsSummaryBucket(
                bucket=key,
                closed_count=b["closed_count"],
                fresh_close_count=b["fresh_close_count"],
                reclose_count=b["reclose_count"],
                reopened_count=b["reopened_count"],
                customer_reopened_count=b["customer_reopened_count"],
                avg_time_to_first_close_minutes=(
                    sum(b["first_close_minutes"]) / len(b["first_close_minutes"]) if b["first_close_minutes"] else None
                ),
                avg_time_to_final_close_minutes=(
                    sum(b["final_close_minutes"]) / len(b["final_close_minutes"]) if b["final_close_minutes"] else None
                ),
            )
        )
    return out


@router.get("/analytics/timeseries", response_model=list[TimeseriesPoint])
async def analytics_timeseries(
    metric: str = Query("closed", pattern="^(closed|reopened|customer_reopens)$"),
    granularity: str = Query("day", pattern="^(day|month|year)$"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
):
    summary = await analytics_summary(period=granularity, date_from=date_from, date_to=date_to, session=session)
    field = {"closed": "closed_count", "reopened": "reopened_count", "customer_reopens": "customer_reopened_count"}[metric]
    return [TimeseriesPoint(bucket=b.bucket, value=getattr(b, field)) for b in summary]

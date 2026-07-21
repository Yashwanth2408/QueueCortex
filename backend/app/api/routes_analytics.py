"""Analytics rollups. "Closed" is only counted for tickets genuinely sitting
CLOSED/REJECTED right now, bucketed by the reporting-date of their last close
event - a ticket that closed and later got reopened again is correctly
excluded, same rule as the Dashboard's "closed today" card. Response/close
duration metrics are built the same way, from `status_transitions` /
`assignment_events` / `ticket_events`, never from Trinity fields it doesn't
actually have."""

from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings
from app.config import Settings
from app.db import get_session
from app.derive import actually_closed_entries, compute_final_close_durations, compute_response_durations
from app.models import StatusTransition, Ticket
from app.schemas import AnalyticsSummaryBucket, TimeseriesPoint

router = APIRouter(tags=["analytics"])


def _bucket_key(d: date, period: str) -> str:
    if period == "day":
        return d.isoformat()
    if period == "month":
        return f"{d.year:04d}-{d.month:02d}"
    return f"{d.year:04d}"


async def _load_reopen_events(session: AsyncSession, date_from: date | None, date_to: date | None):
    stmt = (
        select(StatusTransition)
        .join(Ticket, Ticket.id == StatusTransition.ticket_id)
        .where(StatusTransition.is_reopen.is_(True), Ticket.is_tracked.is_(True))
    )
    rows = (await session.execute(stmt)).scalars().all()
    reopen_events = [
        {"ticket_id": r.ticket_id, "event_date": r.event_date, "is_customer_triggered": r.is_customer_triggered_reopen} for r in rows
    ]
    if date_from:
        reopen_events = [e for e in reopen_events if e["event_date"] >= date_from]
    if date_to:
        reopen_events = [e for e in reopen_events if e["event_date"] <= date_to]
    return reopen_events


@router.get("/analytics/summary", response_model=list[AnalyticsSummaryBucket])
async def analytics_summary(
    period: str = Query("day", pattern="^(day|month|year)$"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
):
    closed_entries = await actually_closed_entries(session, settings)
    if date_from:
        closed_entries = [e for e in closed_entries if e.last_close_date >= date_from]
    if date_to:
        closed_entries = [e for e in closed_entries if e.last_close_date <= date_to]

    reopen_events = await _load_reopen_events(session, date_from, date_to)
    response_durations = await compute_response_durations(session, settings)
    final_close_durations = await compute_final_close_durations(session, settings)

    buckets: dict[str, dict] = defaultdict(
        lambda: {
            "closed_count": 0,
            "fresh_close_count": 0,
            "reclose_count": 0,
            "reopened_count": 0,
            "customer_reopened_count": 0,
            "respond_minutes": [],
            "final_close_minutes": [],
        }
    )

    for e in closed_entries:
        key = _bucket_key(e.last_close_date, period)
        b = buckets[key]
        b["closed_count"] += 1
        if e.total_close_count == 1:
            b["fresh_close_count"] += 1
        else:
            b["reclose_count"] += 1

    for e in reopen_events:
        key = _bucket_key(e["event_date"], period)
        b = buckets[key]
        b["reopened_count"] += 1
        if e["is_customer_triggered"]:
            b["customer_reopened_count"] += 1

    for d in response_durations:
        if date_from and d["date"] < date_from:
            continue
        if date_to and d["date"] > date_to:
            continue
        buckets[_bucket_key(d["date"], period)]["respond_minutes"].append(d["minutes"])

    for d in final_close_durations:
        if date_from and d["date"] < date_from:
            continue
        if date_to and d["date"] > date_to:
            continue
        buckets[_bucket_key(d["date"], period)]["final_close_minutes"].append(d["minutes"])

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
                avg_time_to_respond_minutes=(sum(b["respond_minutes"]) / len(b["respond_minutes"]) if b["respond_minutes"] else None),
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
    settings: Settings = Depends(get_app_settings),
):
    summary = await analytics_summary(period=granularity, date_from=date_from, date_to=date_to, session=session, settings=settings)
    field = {"closed": "closed_count", "reopened": "reopened_count", "customer_reopens": "customer_reopened_count"}[metric]
    return [TimeseriesPoint(bucket=b.bucket, value=getattr(b, field)) for b in summary]

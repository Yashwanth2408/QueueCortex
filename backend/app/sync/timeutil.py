from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    """Naive UTC 'now', matching Trinity's own naive-UTC timestamp convention."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_trinity_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def to_reporting_date(dt_utc_naive: datetime, tz_name: str) -> date:
    aware_utc = dt_utc_naive.replace(tzinfo=timezone.utc)
    local = aware_utc.astimezone(ZoneInfo(tz_name))
    return local.date()


def to_reporting_datetime(dt_utc_naive: datetime, tz_name: str) -> datetime:
    """Like to_reporting_date, but keeps the wall-clock time - needed for
    Shift Watch's shift-start/end comparisons, not just day attribution."""
    aware_utc = dt_utc_naive.replace(tzinfo=timezone.utc)
    local = aware_utc.astimezone(ZoneInfo(tz_name))
    return local.replace(tzinfo=None)

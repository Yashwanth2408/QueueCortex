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

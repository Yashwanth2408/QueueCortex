"""L2 shift-roster CSV parsing and shift-status computation for the "Shift
Watch" feature. Nothing here touches Trinity or the database directly -
pure parsing/derivation, so it's easy to test against the real CSV shape.

The CSV is a flattened export of a multi-block spreadsheet: one block per
shift (e.g. "6A-3P SHIFT (L2)"), each with a title row, a header row
(`Agent,Email,Role,Fixed Weekly Off,<date columns...>`), data rows, then
`On duty (count)`/`Off (count)` summary rows and a blank separator before
the next block. There's also unrelated trailing content (buddy-pairing
tables) which is skipped automatically since it never matches the header
or data row shape."""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

HEADER_PREFIX = ["agent", "email", "role", "fixed weekly off"]

MONTH_ABBR = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

DATE_COL_RE = re.compile(r"^\s*(\d{1,2})-([A-Za-z]{3})\s*:\s*\w+\s*$")
SHIFT_CODE_RE = re.compile(r"^\s*(\d{1,2})(A|P)\s*-\s*(\d{1,2})(A|P)\s*$", re.IGNORECASE)


def _parse_date_columns(header_cells: list[str], base_year: int) -> list[date | None]:
    result: list[date | None] = []
    year = base_year
    prev_month: int | None = None
    for cell in header_cells:
        m = DATE_COL_RE.match(cell)
        if not m:
            result.append(None)
            continue
        month = MONTH_ABBR.get(m.group(2).title())
        if month is None:
            result.append(None)
            continue
        if prev_month is not None and month < prev_month:
            year += 1
        prev_month = month
        result.append(date(year, month, int(m.group(1))))
    return result


def parse_roster_csv(text: str, base_year: int) -> tuple[list[dict], list[dict]]:
    """Returns (agents, shifts): agents is a deduped-by-email list of
    {email, name, role}; shifts is a list of {agent_email, shift_date,
    shift_code}. base_year seeds year inference for the "D-Mon : Day"
    date columns, which carry no year of their own; a month rollback
    (e.g. Dec -> Jan) within one block's date columns increments the year."""
    reader = csv.reader(io.StringIO(text))
    agents: dict[str, dict] = {}
    shifts: list[dict] = []
    date_columns: list[date | None] | None = None

    for row in reader:
        if len(row) < 4:
            date_columns = None
            continue
        first_four = [c.strip().lower() for c in row[:4]]
        if first_four == HEADER_PREFIX:
            date_columns = _parse_date_columns(row[4:], base_year)
            continue
        if date_columns is None:
            continue
        email = row[1].strip().lower() if len(row) > 1 else ""
        if "@" not in email:
            date_columns = None
            continue
        agents[email] = {"email": email, "name": row[0].strip(), "role": row[2].strip() if len(row) > 2 else ""}
        for i, code in enumerate(row[4:]):
            if i >= len(date_columns):
                break
            d = date_columns[i]
            code = code.strip()
            if d is None or not code:
                continue
            shifts.append({"agent_email": email, "shift_date": d, "shift_code": code})

    # Dedup (agent_email, shift_date) - last write wins if it somehow appears twice.
    deduped: dict[tuple[str, date], dict] = {(s["agent_email"], s["shift_date"]): s for s in shifts}
    return list(agents.values()), list(deduped.values())


@dataclass(frozen=True)
class ShiftTimes:
    start_hour: int
    end_hour: int
    crosses_midnight: bool


def parse_shift_code(code: str | None) -> ShiftTimes | None:
    """Recognizes codes like "6A-3P", "11A-8P", "9P-6A" (case-insensitive).
    Anything else - "Off", "EL", blank, or any future leave code - returns
    None ("not a working shift"), so we never need to hardcode every
    possible leave-code string."""
    if not code:
        return None
    m = SHIFT_CODE_RE.match(code)
    if not m:
        return None

    def to_hour_24(hour_12: int, meridiem: str) -> int:
        h = hour_12 % 12
        return h + 12 if meridiem.upper() == "P" else h

    start_hour = to_hour_24(int(m.group(1)), m.group(2))
    end_hour = to_hour_24(int(m.group(3)), m.group(4))
    return ShiftTimes(start_hour=start_hour, end_hour=end_hour, crosses_midnight=end_hour <= start_hour)


def _shift_window(shift_date: date, times: ShiftTimes) -> tuple[datetime, datetime]:
    start = datetime.combine(shift_date, datetime.min.time()).replace(hour=times.start_hour)
    end_date = shift_date + timedelta(days=1) if times.crosses_midnight else shift_date
    end = datetime.combine(end_date, datetime.min.time()).replace(hour=times.end_hour)
    return start, end


@dataclass(frozen=True)
class ShiftStatus:
    on_shift: bool
    reason: str  # 'on_shift' | 'shift_ended' | 'off_day' | 'before_shift_start' | 'no_data'
    shift_label: str | None  # the raw roster code that determined this - e.g. "6A-3P", "Off"


def compute_shift_status(now_local: datetime, today_code: str | None, yesterday_code: str | None) -> ShiftStatus:
    """now_local must already be in the reporting timezone (naive local
    wall-clock). today_code/yesterday_code are the raw roster_shifts rows
    for the agent on now_local's date and the day before, or None if no
    roster row exists for that date."""
    if today_code is None:
        # No roster data for today (out of the uploaded date range, or
        # agent not in the roster at all) - can't make a determination,
        # so don't flag rather than risk a false positive.
        return ShiftStatus(on_shift=True, reason="no_data", shift_label=None)

    shift_date = now_local.date()
    candidates: list[tuple[datetime, datetime, str]] = []

    yesterday_times = parse_shift_code(yesterday_code)
    if yesterday_times and yesterday_times.crosses_midnight:
        y_start, y_end = _shift_window(shift_date - timedelta(days=1), yesterday_times)
        candidates.append((y_start, y_end, yesterday_code))

    today_times = parse_shift_code(today_code)
    if today_times:
        t_start, t_end = _shift_window(shift_date, today_times)
        candidates.append((t_start, t_end, today_code))

    for start, end, label in candidates:
        if start <= now_local < end:
            return ShiftStatus(on_shift=True, reason="on_shift", shift_label=label)

    if today_times is None:
        return ShiftStatus(on_shift=False, reason="off_day", shift_label=today_code)

    t_start, _ = _shift_window(shift_date, today_times)
    if now_local < t_start:
        return ShiftStatus(on_shift=False, reason="before_shift_start", shift_label=today_code)
    return ShiftStatus(on_shift=False, reason="shift_ended", shift_label=today_code)


# ---------------------------------------------------------------------------
# Tag-based type override + red-alert detection (Shift Watch only, per user)
# ---------------------------------------------------------------------------

TYPE_OVERRIDE_TAGS = {"prodsos": "ProdSOS", "sos": "SOS"}
ALERT_TAGS = {"prodsos", "soslegal", "legalcomplaint"}


def _normalize_tag(tag: str) -> str:
    return re.sub(r"[^a-z0-9]", "", tag.lower())


def classify_tags(tags: list[str] | None) -> tuple[str | None, list[str]]:
    """Returns (type_override, matched_alert_tags) for a ticket's raw tag
    list. type_override is "ProdSOS"/"SOS" if a matching tag is present
    (ProdSOS takes precedence if both are somehow present), else None.
    matched_alert_tags lists the original (non-normalized) tags that
    trigger the red-alert symbol."""
    if not tags:
        return None, []
    type_override: str | None = None
    alert_tags: list[str] = []
    for tag in tags:
        normalized = _normalize_tag(tag)
        if normalized in TYPE_OVERRIDE_TAGS and (type_override is None or normalized == "prodsos"):
            type_override = TYPE_OVERRIDE_TAGS[normalized]
        if normalized in ALERT_TAGS:
            alert_tags.append(tag)
    return type_override, alert_tags

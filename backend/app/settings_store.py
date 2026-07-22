"""Runtime-editable settings, persisted in the `settings` table.

Seeded from app.config.Settings (env vars) on first run; after that, values
in the DB win, so a user edit in the Settings UI takes effect without
restarting the app (except poll_interval_minutes, which the scheduler
re-reads on its own interval tick).
"""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Setting
from app.sync.timeutil import utcnow

DEFAULT_KEYS = (
    "trinity_ticket_url_template",
    "poll_interval_minutes",
    "tracked_agent_email",
    "reporting_timezone",
    "sla_thresholds_json",
    "roster_bucket_unassigned_id",
    "roster_bucket_assigned_id",
    "my_shift_json",
)

DEFAULT_MY_SHIFT = {"shift_code": None, "valid_from": None, "valid_to": None, "day_off": None}

# The two Trinity buckets that define "L2, non-Expo" tickets - Shift Watch's
# sync trusts these buckets' own rule_tree (status/level/tag filtering)
# entirely rather than reconstructing the same logic locally. Editable in
# Settings if the bucket IDs ever change.
DEFAULT_ROSTER_BUCKET_UNASSIGNED_ID = "6a29827da9ddae0205369234"  # "L2 - Unassigned Tickets"
DEFAULT_ROSTER_BUCKET_ASSIGNED_ID = "6a2a8529475d4c85de8c9213"  # "L2 - Assigned (New Assigned + Re-opens)"


async def seed_defaults(session: AsyncSession, settings: Settings) -> None:
    defaults = {
        "trinity_ticket_url_template": settings.trinity_ticket_url_template,
        "poll_interval_minutes": settings.poll_interval_minutes,
        "tracked_agent_email": settings.tracked_agent_email,
        "reporting_timezone": settings.reporting_timezone,
        "sla_thresholds_json": {"OPEN": 24, "PENDING": 48},
        "roster_bucket_unassigned_id": DEFAULT_ROSTER_BUCKET_UNASSIGNED_ID,
        "roster_bucket_assigned_id": DEFAULT_ROSTER_BUCKET_ASSIGNED_ID,
        "my_shift_json": DEFAULT_MY_SHIFT,
    }
    existing = (await session.execute(select(Setting.key))).scalars().all()
    existing_set = set(existing)
    now = utcnow()
    for key, value in defaults.items():
        if key not in existing_set:
            session.add(Setting(key=key, value=json.dumps(value), updated_at=now))
    await session.commit()


async def get_all(session: AsyncSession) -> dict:
    rows = (await session.execute(select(Setting))).scalars().all()
    return {r.key: json.loads(r.value) for r in rows}


async def get_value(session: AsyncSession, key: str, default=None):
    row = (await session.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
    if row is None:
        return default
    return json.loads(row.value)


async def set_value(session: AsyncSession, key: str, value) -> None:
    row = (await session.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
    now = utcnow()
    if row is None:
        session.add(Setting(key=key, value=json.dumps(value), updated_at=now))
    else:
        row.value = json.dumps(value)
        row.updated_at = now
    await session.commit()

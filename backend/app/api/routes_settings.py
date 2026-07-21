from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_scheduler
from app.db import get_session
from app.schemas import SettingOut, SettingUpdate
from app.settings_store import get_all, set_value

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=list[SettingOut])
async def list_settings(session: AsyncSession = Depends(get_session)):
    values = await get_all(session)
    return [SettingOut(key=k, value=v) for k, v in values.items()]


@router.put("/settings/{key}", response_model=SettingOut)
async def update_setting(key: str, body: SettingUpdate, session: AsyncSession = Depends(get_session), scheduler=Depends(get_scheduler)):
    await set_value(session, key, body.value)
    if key == "poll_interval_minutes":
        scheduler.reschedule(int(body.value))
    return SettingOut(key=key, value=body.value)

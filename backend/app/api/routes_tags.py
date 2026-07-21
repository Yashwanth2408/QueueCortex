from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Tag, TagTypeMapping, TicketTag
from app.schemas import TagMappingOut, TagMappingUpsert, TagOut
from app.sync.engine import recompute_all_derived_types
from app.sync.timeutil import utcnow

router = APIRouter(tags=["tags"])


@router.get("/tags", response_model=list[TagOut])
async def list_tags(session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(Tag.tag_id, Tag.label, func.count(TicketTag.ticket_id))
            .outerjoin(TicketTag, TicketTag.tag_id == Tag.tag_id)
            .group_by(Tag.tag_id, Tag.label)
            .order_by(Tag.label)
        )
    ).all()
    return [TagOut(tag_id=r[0], label=r[1], ticket_count=r[2]) for r in rows]


@router.get("/tag-mappings", response_model=list[TagMappingOut])
async def list_tag_mappings(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(TagTypeMapping).order_by(TagTypeMapping.priority))).scalars().all()
    return rows


@router.put("/tag-mappings", response_model=list[TagMappingOut])
async def replace_tag_mappings(body: list[TagMappingUpsert], session: AsyncSession = Depends(get_session)):
    now = utcnow()
    existing = (await session.execute(select(TagTypeMapping))).scalars().all()
    existing_by_id = {m.tag_id: m for m in existing}
    wanted_ids = {m.tag_id for m in body}

    for m in existing:
        if m.tag_id not in wanted_ids:
            await session.delete(m)

    for item in body:
        row = existing_by_id.get(item.tag_id)
        if row is None:
            session.add(
                TagTypeMapping(tag_id=item.tag_id, type_label=item.type_label, priority=item.priority, updated_at=now)
            )
        else:
            row.type_label = item.type_label
            row.priority = item.priority
            row.updated_at = now

    await session.commit()
    await recompute_all_derived_types(session)

    rows = (await session.execute(select(TagTypeMapping).order_by(TagTypeMapping.priority))).scalars().all()
    return rows

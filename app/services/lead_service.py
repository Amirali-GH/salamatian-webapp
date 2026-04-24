from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead, LeadStatus, LeadType
from app.schemas.lead import LeadUpdate


async def create_lead(
    db: AsyncSession,
    *,
    type_: LeadType,
    payload_dict: dict,
    images: list[str] | None = None,
) -> Lead:
    lead = Lead(type=type_, images_json=images or [], **payload_dict)
    db.add(lead)
    await db.flush()
    return lead


async def list_leads(
    db: AsyncSession,
    *,
    type_: LeadType | None = None,
    status: LeadStatus | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[Lead], int]:
    stmt = select(Lead)
    if type_:
        stmt = stmt.where(Lead.type == type_)
    if status:
        stmt = stmt.where(Lead.status == status)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(stmt.order_by(Lead.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return list(rows), total


async def get_lead(db: AsyncSession, lead_id: int) -> Lead | None:
    return (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()


async def update_lead(db: AsyncSession, lead: Lead, payload: LeadUpdate) -> Lead:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    return lead

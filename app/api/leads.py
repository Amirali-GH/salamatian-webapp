from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.cache import get_redis
from app.core.permissions import require_operator
from app.database import get_db
from app.models import LeadStatus, LeadType, User
from app.schemas.lead import (
    ConsultationLeadCreate,
    LeadListResponse,
    LeadOut,
    LeadUpdate,
    SellLeadCreate,
)
from app.services import lead_service, media

router = APIRouter(tags=["public"])
admin_router = APIRouter(prefix="/api/admin/leads", tags=["admin"])
router.include_router(admin_router)


async def _rate_limit(request: Request, key_suffix: str) -> None:
    r = await get_redis()
    ip = request.client.host if request.client else "unknown"
    key = f"rl:lead:{key_suffix}:{ip}"
    n = await r.incr(key)
    if n == 1:
        await r.expire(key, 3600)
    if n > settings.PUBLIC_LEAD_RATE_PER_HOUR:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


@router.post("/api/leads/consultation", response_model=LeadOut)
async def create_consultation(
    request: Request,
    payload: ConsultationLeadCreate,
    db: AsyncSession = Depends(get_db),
):
    await _rate_limit(request, "consultation")
    lead = await lead_service.create_lead(
        db,
        type_=LeadType.consultation,
        payload_dict=payload.model_dump(),
    )
    from app.workers.tasks import notify_task

    await db.commit()
    notify_task.delay(
        title="درخواست مشاوره جدید",
        body=f"{lead.name} — {lead.phone}",
        meta={"lead_id": lead.id, "type": "consultation"},
    )
    return lead


@router.post("/api/leads/sell", response_model=LeadOut)
async def create_sell_request(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    car_brand: str | None = Form(None),
    car_model: str | None = Form(None),
    year: int | None = Form(None),
    mileage: int | None = Form(None),
    color: str | None = Form(None),
    description: str | None = Form(None),
    images: list[UploadFile] = File(default_factory=list),
    db: AsyncSession = Depends(get_db),
):
    await _rate_limit(request, "sell")
    payload = SellLeadCreate(
        name=name, phone=phone, car_brand=car_brand, car_model=car_model,
        year=year, mileage=mileage, color=color, description=description,
    )
    saved_images = await media.save_lead_images(images) if images else []
    lead = await lead_service.create_lead(
        db,
        type_=LeadType.sell_request,
        payload_dict=payload.model_dump(),
        images=saved_images,
    )
    from app.workers.tasks import notify_task

    await db.commit()
    notify_task.delay(
        title="درخواست فروش خودرو",
        body=f"{lead.name} — {lead.phone} — {lead.car_brand or ''} {lead.car_model or ''}",
        meta={"lead_id": lead.id, "type": "sell_request"},
    )
    return lead


# ─── Admin ───────────────────────────────────────────────────

@admin_router.get("", response_model=LeadListResponse)
async def admin_list(
    type: LeadType | None = None,
    status: LeadStatus | None = None,
    limit: int = 25,
    offset: int = 0,
    user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await lead_service.list_leads(
        db, type_=type, status=status, limit=limit, offset=offset
    )
    return LeadListResponse(items=rows, total=total, limit=limit, offset=offset)


@admin_router.patch("/{lead_id}", response_model=LeadOut)
async def admin_update(
    lead_id: int,
    payload: LeadUpdate,
    user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    lead = await lead_service.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404)
    await lead_service.update_lead(db, lead, payload)
    await db.commit()
    await db.refresh(lead)
    return lead

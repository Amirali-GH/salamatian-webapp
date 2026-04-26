from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin._deps import admin_user_or_redirect
from app.database import get_db
from app.models import LeadStatus, LeadType
from app.schemas.lead import LeadUpdate
from app.services import lead_service

router = APIRouter(prefix="/admin/leads", tags=["admin"], include_in_schema=False)


@router.get("")
async def leads_list(
    request: Request,
    type: str | None = None,
    status_: str | None = None,
    limit: int = 25,
    offset: int = 0,
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    rows, total = await lead_service.list_leads(
        db,
        type_=LeadType(type) if type else None,
        status=LeadStatus(status_) if status_ else None,
        limit=limit,
        offset=offset,
    )
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "admin/leads.html",
        {
            "user": user_or_redirect,
            "leads": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
            "statuses": [s.value for s in LeadStatus],
            "types": [t.value for t in LeadType],
        },
    )


@router.post("/{lead_id}/update")
async def lead_update(
    lead_id: int,
    status_: str = Form(...),
    operator_note: str | None = Form(None),
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    lead = await lead_service.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404)
    await lead_service.update_lead(
        db, lead, LeadUpdate(status=LeadStatus(status_), operator_note=operator_note)
    )
    await db.commit()
    return RedirectResponse(url="/admin/leads", status_code=303)

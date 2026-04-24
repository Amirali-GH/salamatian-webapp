from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin._deps import admin_user_or_redirect
from app.database import get_db
from app.models import AuditLog, ExcelImportLog

router = APIRouter(prefix="/admin/logs", tags=["admin"], include_in_schema=False)


@router.get("")
async def logs_page(
    request: Request,
    tab: str = "audit",
    entity_type: str | None = None,
    entity_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    audit: list = []
    excel_logs: list = []

    if tab == "audit":
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        audit = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    else:
        excel_logs = (
            await db.execute(
                select(ExcelImportLog).order_by(ExcelImportLog.created_at.desc()).limit(limit).offset(offset)
            )
        ).scalars().all()

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "admin/logs.html",
        {
            "request": request,
            "user": user_or_redirect,
            "tab": tab,
            "audit": audit,
            "excel_logs": excel_logs,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "limit": limit,
            "offset": offset,
        },
    )

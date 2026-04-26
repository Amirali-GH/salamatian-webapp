from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin._deps import admin_user_or_redirect
from app.database import get_db
from app.models import ExcelImportLog, UserRole
from app.services import excel_sync, media

router = APIRouter(prefix="/admin/excel", tags=["admin"], include_in_schema=False)


@router.get("")
async def excel_page(
    request: Request,
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    logs = (
        await db.execute(select(ExcelImportLog).order_by(ExcelImportLog.created_at.desc()).limit(20))
    ).scalars().all()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "admin/excel_import.html",
        {"user": user_or_redirect, "logs": logs, "error": None},
    )


@router.post("/upload")
async def excel_upload(
    request: Request,
    file: UploadFile,
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    if user_or_redirect.role not in (UserRole.admin, UserRole.operator):
        raise HTTPException(status_code=403)
    path = await media.save_excel_upload(file)
    templates = request.app.state.templates
    try:
        diff, token = await excel_sync.parse_and_stage(db, path)
    except ValueError as exc:
        logs = (
            await db.execute(select(ExcelImportLog).order_by(ExcelImportLog.created_at.desc()).limit(20))
        ).scalars().all()
        return templates.TemplateResponse(
            request,
            "admin/excel_import.html",
            {"user": user_or_redirect, "logs": logs, "error": str(exc)},
            status_code=400,
        )
    return RedirectResponse(url=f"/admin/excel/preview/{token}", status_code=303)


@router.get("/preview/{token}")
async def excel_preview(
    request: Request,
    token: str,
    user_or_redirect=Depends(admin_user_or_redirect),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    payload = await excel_sync.load_diff(token)
    if not payload:
        raise HTTPException(status_code=404, detail="Preview expired")
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "admin/excel_preview.html",
        {
            "user": user_or_redirect,
            "token": token,
            "diff": payload["diff"],
            "file_path": payload["file_path"],
        },
    )


@router.post("/apply/{token}")
async def excel_apply(
    token: str,
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    if user_or_redirect.role not in (UserRole.admin, UserRole.operator):
        raise HTTPException(status_code=403)
    try:
        await excel_sync.apply_diff(db, token, user_or_redirect.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url="/admin/excel", status_code=303)

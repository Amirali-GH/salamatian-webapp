from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_admin, require_operator
from app.database import get_db
from app.models import ExcelImportLog, User
from app.services import excel_sync, media

router = APIRouter(prefix="/api/admin/excel", tags=["admin"])


@router.post("/upload")
async def upload_excel(
    file: UploadFile,
    user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    path = await media.save_excel_upload(file)
    try:
        diff, token = await excel_sync.parse_and_stage(db, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "token": token,
        "summary": {
            "new": len(diff["new_cars"]),
            "updated": len(diff["updated_cars"]),
            "removed": len(diff["removed_cars"]),
            "unchanged": diff["unchanged"],
            "warnings": len(diff["warnings"]),
        },
        "diff": diff,
    }


@router.post("/apply")
async def apply_excel(
    token: str,
    user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await excel_sync.apply_diff(db, token, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/logs")
async def excel_logs(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(ExcelImportLog).order_by(ExcelImportLog.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "file_path": r.file_path,
                "imported_rows": r.imported_rows,
                "added_rows": r.added_rows,
                "updated_rows": r.updated_rows,
                "removed_rows": r.removed_rows,
                "warnings": r.warnings,
                "applied_by_user_id": r.applied_by_user_id,
                "applied_at": r.applied_at.isoformat() if r.applied_at else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.get("/download/{log_id}")
async def download_excel(
    log_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from pathlib import Path

    from fastapi.responses import FileResponse

    row = (
        await db.execute(select(ExcelImportLog).where(ExcelImportLog.id == log_id))
    ).scalar_one_or_none()
    if not row or not Path(row.file_path).exists():
        raise HTTPException(status_code=404)
    return FileResponse(row.file_path, filename=Path(row.file_path).name)

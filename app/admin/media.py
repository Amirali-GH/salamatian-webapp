from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.admin._deps import admin_user_or_redirect
from app.config import settings

router = APIRouter(prefix="/admin/media", tags=["admin"], include_in_schema=False)


def _list_dir(root: Path, rel: str = "") -> tuple[list[dict], list[dict]]:
    target = (root / rel).resolve()
    if not str(target).startswith(str(root.resolve())):
        return [], []
    dirs, files = [], []
    if target.exists() and target.is_dir():
        for p in sorted(target.iterdir()):
            entry = {"name": p.name, "rel": str(Path(rel) / p.name)}
            (dirs if p.is_dir() else files).append(entry)
    return dirs, files


@router.get("")
async def media_page(
    request: Request,
    path: str = "",
    user_or_redirect=Depends(admin_user_or_redirect),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    dirs, files = _list_dir(settings.STORAGE_ROOT, path)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "admin/media.html",
        {
            "request": request,
            "user": user_or_redirect,
            "path": path,
            "dirs": dirs,
            "files": files,
        },
    )

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin._deps import admin_user_or_redirect
from app.core.security import hash_password
from app.database import get_db
from app.models import User, UserRole

router = APIRouter(prefix="/admin/settings", tags=["admin"], include_in_schema=False)


@router.get("")
async def settings_page(
    request: Request,
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    if user_or_redirect.role != UserRole.admin:
        raise HTTPException(status_code=403)
    users = (await db.execute(select(User).order_by(User.id))).scalars().all()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "admin/settings.html",
        {
            "user": user_or_redirect,
            "users": users,
            "roles": [r.value for r in UserRole],
        },
    )


@router.post("/users/new")
async def create_user(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("viewer"),
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    if user_or_redirect.role != UserRole.admin:
        raise HTTPException(status_code=403)
    existing = (
        await db.execute(select(User).where((User.username == username) | (User.email == email)))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already exists")
    db.add(
        User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=UserRole(role),
            is_active=True,
        )
    )
    await db.commit()
    return RedirectResponse(url="/admin/settings", status_code=303)


@router.post("/users/{user_id}/toggle")
async def toggle_user(
    user_id: int,
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    if user_or_redirect.role != UserRole.admin:
        raise HTTPException(status_code=403)
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404)
    target.is_active = not target.is_active
    await db.commit()
    return RedirectResponse(url="/admin/settings", status_code=303)

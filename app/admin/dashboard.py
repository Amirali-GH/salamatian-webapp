from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin._deps import admin_user_or_redirect
from app.config import settings
from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.models import AuditLog, Car, CarStatus, Lead, LeadStatus, User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"], include_in_schema=False)


@router.get("/login")
async def login_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse("admin/login.html", {"request": request, "error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    templates = request.app.state.templates
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "admin/login.html",
            {"request": request, "error": "نام کاربری یا رمز عبور نادرست است"},
            status_code=401,
        )
    token = create_access_token(user.id, user.role.value)
    response = RedirectResponse(url="/admin/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return response


@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("access_token", path="/")
    return response


@router.get("/")
async def dashboard(
    request: Request,
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user: User = user_or_redirect

    total_cars = (await db.execute(select(func.count(Car.id)).where(Car.deleted_at.is_(None)))).scalar_one()
    pending_cars = (
        await db.execute(
            select(func.count(Car.id)).where(Car.status == CarStatus.pending, Car.deleted_at.is_(None))
        )
    ).scalar_one()
    published_cars = (
        await db.execute(
            select(func.count(Car.id)).where(Car.status == CarStatus.published, Car.deleted_at.is_(None))
        )
    ).scalar_one()
    new_leads = (
        await db.execute(select(func.count(Lead.id)).where(Lead.status == LeadStatus.new))
    ).scalar_one()
    recent_activity = (
        await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10))
    ).scalars().all()

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "user": user,
            "total_cars": total_cars,
            "pending_cars": pending_cars,
            "published_cars": published_cars,
            "new_leads": new_leads,
            "recent_activity": recent_activity,
        },
    )

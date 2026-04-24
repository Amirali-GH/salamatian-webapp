from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import get_current_user
from app.database import get_db
from app.models import User, UserRole


def templates_dep(request: Request) -> Jinja2Templates:
    return request.app.state.templates


async def admin_user_or_redirect(request: Request, db: AsyncSession = Depends(get_db)) -> User | RedirectResponse:
    """Return the current user OR a RedirectResponse to /admin/login.

    Admin HTML routes must handle the returned type — this keeps the redirect
    inside the response layer (instead of raising from a dependency).
    """
    token = request.cookies.get("access_token")
    auth = request.headers.get("authorization")
    try:
        return await get_current_user(authorization=auth, access_token=token, db=db)
    except Exception:
        return RedirectResponse(url="/admin/login", status_code=303)


def require_admin_role(*allowed: UserRole):
    """HTML-style role gate that returns a 403 template response when denied."""

    async def _check(
        request: Request,
        user_or_redirect: User | RedirectResponse = Depends(admin_user_or_redirect),
    ):
        if isinstance(user_or_redirect, RedirectResponse):
            return user_or_redirect
        if user_or_redirect.role not in allowed:
            templates = request.app.state.templates
            return templates.TemplateResponse(
                "admin/error.html",
                {
                    "request": request,
                    "status_code": 403,
                    "message": "شما اجازه دسترسی به این بخش را ندارید",
                    "request_id": getattr(request.state, "request_id", ""),
                },
                status_code=403,
            )
        return user_or_redirect

    return _check

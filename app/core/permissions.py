from typing import Annotated

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.database import get_db
from app.models import User, UserRole


def _extract_token(authorization: str | None, access_token_cookie: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(None, 1)[1].strip()
    if access_token_cookie:
        return access_token_cookie
    return None


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    access_token: Annotated[str | None, Cookie()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = _extract_token(authorization, access_token)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_optional_user(
    authorization: Annotated[str | None, Header()] = None,
    access_token: Annotated[str | None, Cookie()] = None,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    try:
        return await get_current_user(authorization=authorization, access_token=access_token, db=db)
    except HTTPException:
        return None


def require_role(*roles: UserRole):
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return _check


require_admin = require_role(UserRole.admin)
require_operator = require_role(UserRole.admin, UserRole.operator)
require_any_role = require_role(UserRole.admin, UserRole.operator, UserRole.viewer)


async def admin_html_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """Dependency for admin HTML routes - redirects to /admin/login on failure."""
    token = request.cookies.get("access_token")
    auth_header = request.headers.get("authorization")
    try:
        return await get_current_user(authorization=auth_header, access_token=token, db=db)
    except HTTPException:
        from fastapi.responses import RedirectResponse

        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/admin/login"},
            detail="Redirect to login",
        )

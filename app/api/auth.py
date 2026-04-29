from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import clear_access_token_cookie, set_access_token_cookie
from app.core.permissions import get_current_user
from app.core.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.database import get_db
from app.models import AuditAction, AuditLog, User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user.last_login_at = datetime.now(tz=timezone.utc)
    db.add(AuditLog(user_id=user.id, entity_type="user", entity_id=user.id, action=AuditAction.login))
    await db.commit()

    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id)
    set_access_token_cookie(response, request, access)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        data = decode_token(payload.refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if data.get("type") != REFRESH_TOKEN_TYPE:
        raise HTTPException(status_code=401, detail="Invalid token type")
    user_id = int(data["sub"])
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    access = create_access_token(user.id, user.role.value)
    new_refresh = create_refresh_token(user.id)
    set_access_token_cookie(response, request, access)
    return TokenPair(access_token=access, refresh_token=new_refresh)


@router.post("/logout")
async def logout(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    db.add(AuditLog(user_id=user.id, entity_type="user", entity_id=user.id, action=AuditAction.logout))
    await db.commit()
    clear_access_token_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user

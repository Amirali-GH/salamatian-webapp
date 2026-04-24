from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def _encode(payload: dict[str, Any], expires: timedelta, token_type: str) -> str:
    now = datetime.now(tz=timezone.utc)
    data = payload.copy()
    data.update({"iat": now, "exp": now + expires, "type": token_type})
    return jwt.encode(data, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str | int, role: str) -> str:
    return _encode(
        {"sub": str(subject), "role": role},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        ACCESS_TOKEN_TYPE,
    )


def create_refresh_token(subject: str | int) -> str:
    return _encode(
        {"sub": str(subject)},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        REFRESH_TOKEN_TYPE,
    )


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

from fastapi import Request, Response

from app.config import settings


ACCESS_TOKEN_COOKIE_NAME = "access_token"


def use_secure_cookies(request: Request) -> bool:
    """Match cookie security to the effective request scheme behind proxies."""
    return request.url.scheme == "https"


def set_access_token_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        ACCESS_TOKEN_COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=use_secure_cookies(request),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def clear_access_token_cookie(response: Response) -> None:
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME, path="/")

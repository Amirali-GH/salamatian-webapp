"""Smoke test for the auth API. Uses the real FastAPI app with an aiosqlite
override. Verifies the login → me round trip and role-based 403.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import User, UserRole


@pytest_asyncio.fixture
async def client():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        db.add(
            User(
                username="admin",
                email="admin@example.com",
                password_hash=hash_password("admin123"),
                role=UserRole.admin,
                is_active=True,
            )
        )
        db.add(
            User(
                username="viewer",
                email="viewer@example.com",
                password_hash=hash_password("viewer123"),
                role=UserRole.viewer,
                is_active=True,
            )
        )
        await db.commit()

    async def _get_db():
        async with Session() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    await eng.dispose()


async def test_login_and_me(client: AsyncClient):
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    r2 = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["username"] == "admin"


async def test_login_bad_password(client: AsyncClient):
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


async def test_viewer_cannot_create_car(client: AsyncClient):
    r = await client.post("/api/auth/login", json={"username": "viewer", "password": "viewer123"})
    token = r.json()["access_token"]
    r2 = await client.post(
        "/api/admin/cars",
        headers={"Authorization": f"Bearer {token}"},
        json={"brand": "X", "model": "Y", "year": 1400, "price": "100"},
    )
    assert r2.status_code == 403


async def test_public_cars_empty(client: AsyncClient):
    r = await client.get("/api/cars")
    assert r.status_code == 200
    assert r.json()["total"] == 0

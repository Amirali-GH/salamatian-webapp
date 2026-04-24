"""Shared test fixtures. Uses a fake in-memory Redis and an aiosqlite DB for
the Excel-sync and service-level tests so no external services are required.
"""
from __future__ import annotations

import os
from typing import Any

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}

    async def get(self, k):
        return self.store.get(k)

    async def set(self, k, v, ex: int | None = None):
        self.store[k] = v

    async def delete(self, *keys):
        for k in keys:
            self.store.pop(k, None)

    async def incr(self, k):
        self.store[k] = int(self.store.get(k, 0)) + 1
        return self.store[k]

    async def expire(self, k, ttl):
        return True

    async def scan_iter(self, match: str = "*", count: int = 500):
        prefix = match.rstrip("*")
        for k in list(self.store):
            if k.startswith(prefix):
                yield k


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """Replace the global redis client and notify/invalidate helpers."""
    fake = FakeRedis()

    async def _get():
        return fake

    from app.core import cache as cache_mod

    monkeypatch.setattr(cache_mod, "get_redis", _get)
    monkeypatch.setattr(cache_mod, "_redis", fake, raising=False)

    # Prevent celery .delay() from doing anything during tests
    from app.workers import tasks as tasks_mod

    class _Dummy:
        def delay(self, *a, **kw):
            return None

    monkeypatch.setattr(tasks_mod, "notify_task", _Dummy())
    monkeypatch.setattr(tasks_mod, "image_optimize_task", _Dummy())
    return fake


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        # The JSONB columns fall back to JSON on SQLite automatically via SA 2.x
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncSession:  # type: ignore[misc]
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session

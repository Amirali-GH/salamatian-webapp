"""Pluggable notification channels. Called from Celery tasks so HTTP latency
is not affected. Synchronous internals so this file can be imported by both
async web code (via asyncio.to_thread) and sync Celery tasks.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Protocol

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Notification, NotificationChannel, User, UserRole

log = structlog.get_logger()


class NotificationChannelImpl(Protocol):
    name: str

    def send(self, title: str, body: str, meta: dict | None = None) -> bool: ...


class TelegramChannel:
    name = "telegram"

    def send(self, title: str, body: str, meta: dict | None = None) -> bool:
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            return False
        try:
            resp = httpx.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": settings.TELEGRAM_CHAT_ID,
                    "text": f"<b>{title}</b>\n\n{body}",
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as exc:  # noqa: BLE001
            log.warning("telegram_send_failed", error=str(exc))
            return False


class EmailChannel:
    name = "email"

    def send(self, title: str, body: str, meta: dict | None = None) -> bool:
        if not settings.SMTP_HOST:
            return False
        try:
            msg = EmailMessage()
            msg["Subject"] = title
            msg["From"] = settings.SMTP_FROM
            msg["To"] = settings.SMTP_FROM
            msg.set_content(body)
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as s:
                s.starttls()
                if settings.SMTP_USER:
                    s.login(settings.SMTP_USER, settings.SMTP_PASSWORD or "")
                s.send_message(msg)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("email_send_failed", error=str(exc))
            return False


async def send_admin_panel(
    db: AsyncSession, title: str, body: str, meta: dict | None = None
) -> int:
    users = (
        await db.execute(
            select(User).where(
                User.is_active.is_(True),
                User.role.in_([UserRole.admin, UserRole.operator]),
            )
        )
    ).scalars().all()
    for u in users:
        db.add(
            Notification(
                user_id=u.id,
                channel=NotificationChannel.admin_panel,
                title=title,
                body=body,
                meta=meta or {},
            )
        )
    return len(users)

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
from PIL import Image, ImageOps
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import CarImage, Notification, NotificationChannel, User, UserRole
from app.workers.celery_app import celery_app

log = structlog.get_logger()

IMAGE_SIZES = {"thumb": 300, "medium": 800, "full": 1600}


def _generate_variants(src: Path) -> dict[str, Path]:
    """Create thumb/medium/full WebP variants. Returns a dict {size_name: path}."""
    out: dict[str, Path] = {}
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        for name, max_dim in IMAGE_SIZES.items():
            clone = im.copy()
            clone.thumbnail((max_dim, max_dim))
            dst = src.with_suffix("").with_name(src.stem + f".{name}.webp")
            # Strip EXIF by not passing it
            clone.save(dst, format="WEBP", quality=82, method=6)
            out[name] = dst
    return out


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def image_optimize_task(self, car_image_id: int) -> dict:
    """Generate WebP variants (thumb/medium/full) for an uploaded car image."""

    async def _run() -> dict:
        async with AsyncSessionLocal() as db:
            img = (
                await db.execute(select(CarImage).where(CarImage.id == car_image_id))
            ).scalar_one_or_none()
            if not img:
                return {"status": "missing"}
            src = settings.cars_upload_dir / img.image_path
            if not src.exists():
                return {"status": "file_missing", "path": str(src)}
            try:
                _generate_variants(src)
            except Exception as exc:  # noqa: BLE001
                log.exception("image_optimize_failed", image_id=car_image_id, error=str(exc))
                raise
        return {"status": "ok", "image_id": car_image_id}

    try:
        return asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@celery_app.task
def notify_task(title: str, body: str, meta: dict | None = None) -> int:
    """Persist a notification to every admin/operator user (admin_panel channel)."""

    async def _run() -> int:
        async with AsyncSessionLocal() as db:
            users = (
                await db.execute(
                    select(User).where(
                        User.is_active.is_(True),
                        User.role.in_([UserRole.admin, UserRole.operator]),
                    )
                )
            ).scalars().all()
            for user in users:
                db.add(
                    Notification(
                        user_id=user.id,
                        channel=NotificationChannel.admin_panel,
                        title=title,
                        body=body,
                        meta=meta or {},
                    )
                )
            await db.commit()
            return len(users)

    count = asyncio.run(_run())

    # Optional Telegram
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        try:
            import httpx

            httpx.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": f"{title}\n\n{body}"},
                timeout=10,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("telegram_notify_failed", error=str(exc))
    return count


@celery_app.task
def scan_excel_inbox() -> dict:
    """Daily scan of /storage/uploads/excel/inbox/ for new files.

    The task parses the file in preview mode, logs the diff, and notifies admins.
    It NEVER auto-applies — human approval is required.
    """
    from app.services import excel_sync

    settings.EXCEL_INBOX_DIR.mkdir(parents=True, exist_ok=True)
    inbox = settings.EXCEL_INBOX_DIR
    files = sorted(p for p in inbox.glob("*.xlsx") if p.is_file())
    if not files:
        return {"status": "no_files"}

    async def _process_all() -> dict:
        out = {"files": []}
        async with AsyncSessionLocal() as db:
            for f in files:
                try:
                    diff, token = await excel_sync.parse_and_stage(db, f, scheduled=True)
                    out["files"].append(
                        {
                            "path": str(f),
                            "token": token,
                            "added": len(diff["new_cars"]),
                            "updated": len(diff["updated_cars"]),
                            "removed": len(diff["removed_cars"]),
                            "warnings": len(diff["warnings"]),
                        }
                    )
                    notify_task.delay(
                        title="Excel inbox — diff preview ready",
                        body=(
                            f"File: {f.name}\n"
                            f"New: {len(diff['new_cars'])} / "
                            f"Updated: {len(diff['updated_cars'])} / "
                            f"Removed: {len(diff['removed_cars'])} / "
                            f"Warnings: {len(diff['warnings'])}\n"
                            f"Preview: {settings.BASE_URL}/admin/excel/preview/{token}"
                        ),
                        meta={"token": token, "file": str(f)},
                    )
                except Exception as exc:  # noqa: BLE001
                    log.exception("excel_inbox_parse_failed", file=str(f))
                    out["files"].append({"path": str(f), "error": str(exc)})
        return out

    return asyncio.run(_process_all())

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_any_role
from app.database import get_db
from app.models import Notification, User

router = APIRouter(prefix="/api/admin/notifications", tags=["admin"])


@router.get("/unread")
async def list_unread(
    user: User = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(Notification)
            .where(Notification.user_id == user.id, Notification.is_read.is_(False))
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": n.id,
                "title": n.title,
                "body": n.body,
                "meta": n.meta,
                "created_at": n.created_at.isoformat(),
            }
            for n in rows
        ],
        "count": len(rows),
    }


@router.post("/read-all")
async def mark_all_read(
    user: User = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}

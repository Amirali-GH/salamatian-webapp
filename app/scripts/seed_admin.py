"""Create the bootstrap admin user from env vars, idempotent."""
import asyncio

from sqlalchemy import select

from app.config import settings
from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.models import User, UserRole


async def main() -> None:
    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(select(User).where(User.username == settings.BOOTSTRAP_ADMIN_USERNAME))
        ).scalar_one_or_none()
        if existing:
            print(f"Admin user {existing.username!r} already exists (id={existing.id}).")
            return
        user = User(
            username=settings.BOOTSTRAP_ADMIN_USERNAME,
            email=settings.BOOTSTRAP_ADMIN_EMAIL,
            password_hash=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
            role=UserRole.admin,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        print(f"Created admin user {user.username!r}.")


if __name__ == "__main__":
    asyncio.run(main())

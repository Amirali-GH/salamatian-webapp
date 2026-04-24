import enum

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models._mixins import TimestampMixin
from app.models._types import JSONType


class NotificationChannel(str, enum.Enum):
    admin_panel = "admin_panel"
    telegram = "telegram"
    email = "email"


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, name="notification_channel"),
        nullable=False,
        default=NotificationChannel.admin_panel,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONType, nullable=True, default=dict)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

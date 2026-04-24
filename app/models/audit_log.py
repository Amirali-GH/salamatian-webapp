import enum

from sqlalchemy import BigInteger, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models._mixins import TimestampMixin
from app.models._types import JSONType


class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"
    archive = "archive"
    publish = "publish"
    price_change = "price_change"
    login = "login"
    logout = "logout"


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action"), nullable=False, index=True
    )
    old_value: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

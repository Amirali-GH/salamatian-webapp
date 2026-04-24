from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models._mixins import TimestampMixin
from app.models._types import JSONType


class ExcelImportLog(Base, TimestampMixin):
    __tablename__ = "excel_import_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    added_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    removed_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warnings: Mapped[list | None] = mapped_column(JSONType, nullable=True, default=list)
    applied_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

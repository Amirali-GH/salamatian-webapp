import enum

from sqlalchemy import BigInteger, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models._mixins import TimestampMixin
from app.models._types import JSONType


class LeadType(str, enum.Enum):
    consultation = "consultation"
    sell_request = "sell_request"


class LeadStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    converted = "converted"
    closed = "closed"


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[LeadType] = mapped_column(Enum(LeadType, name="lead_type"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    car_brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    car_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mileage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    images_json: Mapped[list | None] = mapped_column(JSONType, nullable=True, default=list)
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status"), nullable=False, default=LeadStatus.new, index=True
    )
    operator_note: Mapped[str | None] = mapped_column(Text, nullable=True)

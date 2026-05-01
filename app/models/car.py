import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Enum, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._mixins import TimestampMixin
from app.models._types import JSONType


class Gearbox(str, enum.Enum):
    manual = "manual"
    automatic = "automatic"
    cvt = "cvt"
    dct = "dct"


class FuelType(str, enum.Enum):
    gasoline = "gasoline"
    diesel = "diesel"
    hybrid = "hybrid"
    electric = "electric"
    lpg = "lpg"
    cng = "cng"


class CarStatus(str, enum.Enum):
    draft = "draft"
    pending = "pending"
    published = "published"
    archived = "archived"


class CarSource(str, enum.Enum):
    manual = "manual"
    excel = "excel"
    user_submission = "user_submission"


class Car(Base, TimestampMixin):
    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    brand: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    mileage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gearbox: Mapped[Gearbox | None] = mapped_column(Enum(Gearbox, name="gearbox"), nullable=True)
    fuel_type: Mapped[FuelType | None] = mapped_column(Enum(FuelType, name="fuel_type"), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    body_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    engine_volume: Mapped[str | None] = mapped_column(String(50), nullable=True)
    engine_power: Mapped[str | None] = mapped_column(String(50), nullable=True)
    acceleration: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fuel_consumption: Mapped[str | None] = mapped_column(String(50), nullable=True)
    brake_system: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    features_json: Mapped[dict | None] = mapped_column(JSONType, nullable=True, default=dict)
    images_json: Mapped[list | None] = mapped_column(JSONType, nullable=True, default=list)
    status: Mapped[CarStatus] = mapped_column(
        Enum(CarStatus, name="car_status"), nullable=False, default=CarStatus.draft, index=True
    )
    source: Mapped[CarSource] = mapped_column(
        Enum(CarSource, name="car_source"), nullable=False, default=CarSource.manual, index=True
    )
    supplier: Mapped[str | None] = mapped_column(String(150), nullable=True)
    excel_row_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    images = relationship("CarImage", back_populates="car", cascade="all, delete-orphan", order_by="CarImage.sort_order")
    seo = relationship("CarSEO", back_populates="car", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("excel_row_id", name="uq_cars_excel_row_id"),
        Index("ix_cars_brand_model_year", "brand", "model", "year"),
        Index("ix_cars_status_source", "status", "source"),
        Index("ix_cars_created_at", "created_at"),
    )

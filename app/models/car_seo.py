from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._mixins import TimestampMixin
from app.models._types import JSONType


class CarSEO(Base, TimestampMixin):
    __tablename__ = "car_seo"

    car_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("cars.id", ondelete="CASCADE"),
        primary_key=True,
    )
    meta_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    slug: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    schema_json: Mapped[dict | None] = mapped_column(JSONType, nullable=True, default=dict)

    car = relationship("Car", back_populates="seo")

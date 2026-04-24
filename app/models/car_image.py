from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._mixins import TimestampMixin


class CarImage(Base, TimestampMixin):
    __tablename__ = "car_images"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    car_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("cars.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_path: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    car = relationship("Car", back_populates="images")

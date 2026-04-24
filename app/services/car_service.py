from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditAction, AuditLog, Car, CarImage, CarStatus
from app.schemas.car import CarCreate, CarFilters, CarUpdate

SORT_COLUMNS = {
    "created_at": Car.created_at,
    "price": Car.price,
    "year": Car.year,
    "mileage": Car.mileage,
}


def _apply_sort(query, sort: str):
    desc = sort.startswith("-")
    col_name = sort.lstrip("-+")
    col = SORT_COLUMNS.get(col_name, Car.created_at)
    return query.order_by(col.desc() if desc else col.asc())


def _build_filter_clauses(f: CarFilters, only_published: bool = False) -> list:
    clauses = [Car.deleted_at.is_(None)]
    if only_published:
        clauses.append(Car.status == CarStatus.published)
    elif f.status:
        clauses.append(Car.status == f.status)
    if f.brand:
        clauses.append(Car.brand.ilike(f"%{f.brand}%"))
    if f.model:
        clauses.append(Car.model.ilike(f"%{f.model}%"))
    if f.year_min is not None:
        clauses.append(Car.year >= f.year_min)
    if f.year_max is not None:
        clauses.append(Car.year <= f.year_max)
    if f.price_min is not None:
        clauses.append(Car.price >= f.price_min)
    if f.price_max is not None:
        clauses.append(Car.price <= f.price_max)
    if f.gearbox:
        clauses.append(Car.gearbox == f.gearbox)
    if f.fuel_type:
        clauses.append(Car.fuel_type == f.fuel_type)
    if f.location:
        clauses.append(Car.location.ilike(f"%{f.location}%"))
    if f.search:
        like = f"%{f.search}%"
        clauses.append(or_(Car.brand.ilike(like), Car.model.ilike(like), Car.description.ilike(like)))
    return clauses


async def list_cars(db: AsyncSession, filters: CarFilters, only_published: bool = False) -> tuple[list[Car], int]:
    clauses = _build_filter_clauses(filters, only_published=only_published)
    base = select(Car).where(and_(*clauses))
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    query = _apply_sort(base, filters.sort).limit(filters.limit).offset(filters.offset)
    items = (await db.execute(query)).scalars().all()
    return list(items), total


async def get_car(db: AsyncSession, car_id: int, *, include_deleted: bool = False) -> Car | None:
    stmt = select(Car).where(Car.id == car_id)
    if not include_deleted:
        stmt = stmt.where(Car.deleted_at.is_(None))
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_public_car(db: AsyncSession, car_id: int) -> Car | None:
    stmt = select(Car).where(
        Car.id == car_id, Car.deleted_at.is_(None), Car.status == CarStatus.published
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_car(db: AsyncSession, payload: CarCreate, user_id: int | None) -> Car:
    car = Car(**payload.model_dump())
    db.add(car)
    await db.flush()
    db.add(
        AuditLog(
            user_id=user_id,
            entity_type="car",
            entity_id=car.id,
            action=AuditAction.create,
            new_value=payload.model_dump(mode="json"),
        )
    )
    return car


async def update_car(
    db: AsyncSession, car: Car, payload: CarUpdate, user_id: int | None
) -> Car:
    old_data: dict[str, Any] = {}
    new_data: dict[str, Any] = {}
    price_changed = False
    old_price: Decimal | None = None

    for field, value in payload.model_dump(exclude_unset=True).items():
        current = getattr(car, field)
        if current != value:
            old_data[field] = current
            new_data[field] = value
            if field == "price":
                price_changed = True
                old_price = current
            setattr(car, field, value)

    if not new_data:
        return car

    db.add(
        AuditLog(
            user_id=user_id,
            entity_type="car",
            entity_id=car.id,
            action=AuditAction.update,
            old_value={k: str(v) if isinstance(v, Decimal) else v for k, v in old_data.items()},
            new_value={k: str(v) if isinstance(v, Decimal) else v for k, v in new_data.items()},
        )
    )
    if price_changed:
        db.add(
            AuditLog(
                user_id=user_id,
                entity_type="car",
                entity_id=car.id,
                action=AuditAction.price_change,
                old_value={"price": str(old_price)},
                new_value={"price": str(payload.price)},
            )
        )
    return car


async def soft_delete_car(db: AsyncSession, car: Car, user_id: int | None) -> None:
    from datetime import datetime, timezone

    car.deleted_at = datetime.now(tz=timezone.utc)
    db.add(
        AuditLog(
            user_id=user_id, entity_type="car", entity_id=car.id, action=AuditAction.delete,
        )
    )


async def archive_car(db: AsyncSession, car: Car, user_id: int | None) -> None:
    old = car.status
    car.status = CarStatus.archived
    db.add(
        AuditLog(
            user_id=user_id,
            entity_type="car",
            entity_id=car.id,
            action=AuditAction.archive,
            old_value={"status": old.value},
            new_value={"status": CarStatus.archived.value},
        )
    )


async def publish_car(db: AsyncSession, car: Car, user_id: int | None) -> None:
    old = car.status
    car.status = CarStatus.published
    db.add(
        AuditLog(
            user_id=user_id,
            entity_type="car",
            entity_id=car.id,
            action=AuditAction.publish,
            old_value={"status": old.value},
            new_value={"status": CarStatus.published.value},
        )
    )


async def refresh_images_cache(db: AsyncSession, car: Car) -> None:
    images = (
        await db.execute(
            select(CarImage).where(CarImage.car_id == car.id).order_by(CarImage.sort_order.asc())
        )
    ).scalars().all()
    car.images_json = [
        {"id": img.id, "path": img.image_path, "sort_order": img.sort_order} for img in images
    ]

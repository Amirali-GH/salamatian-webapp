from decimal import Decimal

from sqlalchemy import select

from app.models import AuditAction, AuditLog, CarStatus
from app.schemas.car import CarCreate, CarFilters, CarUpdate
from app.services import car_service


async def test_create_and_list_car(db):
    payload = CarCreate(
        brand="Peugeot", model="206", year=1395, price=Decimal("450000000"),
        status=CarStatus.published,
    )
    car = await car_service.create_car(db, payload, user_id=1)
    await db.commit()
    assert car.id is not None

    items, total = await car_service.list_cars(db, CarFilters(), only_published=True)
    assert total == 1
    assert items[0].brand == "Peugeot"


async def test_price_change_writes_audit(db):
    car = await car_service.create_car(
        db,
        CarCreate(brand="K", model="M", year=1400, price=Decimal("100")),
        user_id=1,
    )
    await db.commit()

    await car_service.update_car(
        db, car, CarUpdate(price=Decimal("200")), user_id=1,
    )
    await db.commit()

    logs = (await db.execute(select(AuditLog).where(AuditLog.entity_id == car.id))).scalars().all()
    assert any(l.action == AuditAction.price_change for l in logs)


async def test_soft_delete_sets_deleted_at(db):
    car = await car_service.create_car(
        db, CarCreate(brand="K", model="M", year=1400, price=Decimal("100")), user_id=1,
    )
    await db.commit()
    await car_service.soft_delete_car(db, car, user_id=1)
    await db.commit()
    assert car.deleted_at is not None
    got = await car_service.get_car(db, car.id)
    assert got is None  # filtered out

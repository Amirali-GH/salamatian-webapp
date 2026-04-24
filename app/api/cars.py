from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.cache import cache_get, cache_set, invalidate_cars_cache, make_key
from app.core.permissions import require_operator
from app.database import get_db
from app.models import CarImage, FuelType, Gearbox, User
from app.schemas.car import (
    CarCreate,
    CarFilters,
    CarListResponse,
    CarOut,
    CarUpdate,
)
from app.services import car_service, media

public_router = APIRouter(prefix="/api/cars", tags=["public"])
admin_router = APIRouter(prefix="/api/admin/cars", tags=["admin"])

router = APIRouter()
router.include_router(public_router)
router.include_router(admin_router)


@public_router.get("", response_model=CarListResponse)
async def list_published(
    brand: str | None = None,
    model: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    price_min: Decimal | None = None,
    price_max: Decimal | None = None,
    gearbox: Gearbox | None = None,
    fuel_type: FuelType | None = None,
    location: str | None = None,
    search: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = "-created_at",
    db: AsyncSession = Depends(get_db),
):
    filters = CarFilters(
        brand=brand, model=model, year_min=year_min, year_max=year_max,
        price_min=price_min, price_max=price_max, gearbox=gearbox,
        fuel_type=fuel_type, location=location, search=search,
        limit=limit, offset=offset, sort=sort,
    )
    cache_key = make_key("cars:list:", filters.model_dump(mode="json"))
    cached = await cache_get(cache_key)
    if cached:
        return cached
    items, total = await car_service.list_cars(db, filters, only_published=True)
    response = CarListResponse(
        items=[
            {
                "id": c.id, "brand": c.brand, "model": c.model, "year": c.year,
                "price": c.price, "mileage": c.mileage, "gearbox": c.gearbox,
                "fuel_type": c.fuel_type, "location": c.location, "status": c.status,
                "images_json": c.images_json,
            }
            for c in items
        ],
        total=total, limit=limit, offset=offset,
    ).model_dump(mode="json")
    await cache_set(cache_key, response, ttl=settings.CACHE_TTL_LIST)
    return response


@public_router.get("/{car_id}", response_model=CarOut)
async def get_public_car(car_id: int, db: AsyncSession = Depends(get_db)):
    cache_key = f"cars:detail:{car_id}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    car = await car_service.get_public_car(db, car_id)
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    data = CarOut.model_validate(car).model_dump(mode="json")
    await cache_set(cache_key, data, ttl=settings.CACHE_TTL_DETAIL)
    return data


# ─── Admin ──────────────────────────────────────────────────────────────

@admin_router.post("", response_model=CarOut)
async def admin_create_car(
    payload: CarCreate,
    user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    car = await car_service.create_car(db, payload, user.id)
    await db.commit()
    await db.refresh(car)
    await invalidate_cars_cache()
    return car


@admin_router.patch("/{car_id}", response_model=CarOut)
async def admin_update_car(
    car_id: int,
    payload: CarUpdate,
    user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    car = await car_service.get_car(db, car_id)
    if not car:
        raise HTTPException(status_code=404)
    await car_service.update_car(db, car, payload, user.id)
    await db.commit()
    await db.refresh(car)
    await invalidate_cars_cache()
    return car


@admin_router.delete("/{car_id}")
async def admin_delete_car(
    car_id: int,
    user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    car = await car_service.get_car(db, car_id)
    if not car:
        raise HTTPException(status_code=404)
    await car_service.soft_delete_car(db, car, user.id)
    await db.commit()
    await invalidate_cars_cache()
    return {"ok": True}


@admin_router.post("/{car_id}/publish", response_model=CarOut)
async def admin_publish(
    car_id: int,
    user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    car = await car_service.get_car(db, car_id)
    if not car:
        raise HTTPException(status_code=404)
    await car_service.publish_car(db, car, user.id)
    await db.commit()
    await db.refresh(car)
    await invalidate_cars_cache()
    return car


@admin_router.post("/{car_id}/archive", response_model=CarOut)
async def admin_archive(
    car_id: int,
    user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    car = await car_service.get_car(db, car_id)
    if not car:
        raise HTTPException(status_code=404)
    await car_service.archive_car(db, car, user.id)
    await db.commit()
    await db.refresh(car)
    await invalidate_cars_cache()
    return car


@admin_router.post("/{car_id}/images")
async def admin_upload_images(
    car_id: int,
    images: list[UploadFile],
    user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    car = await car_service.get_car(db, car_id)
    if not car:
        raise HTTPException(status_code=404)
    from app.workers.tasks import image_optimize_task

    existing = car.images_json or []
    start = len(existing)
    created_ids: list[int] = []
    for i, upload in enumerate(images):
        rel = await media.save_car_image(upload, car_id)
        img = CarImage(car_id=car_id, image_path=rel, sort_order=start + i)
        db.add(img)
        await db.flush()
        created_ids.append(img.id)
    await car_service.refresh_images_cache(db, car)
    await db.commit()
    for img_id in created_ids:
        image_optimize_task.delay(img_id)
    await invalidate_cars_cache()
    return {"uploaded": len(created_ids)}


@admin_router.patch("/{car_id}/images/reorder")
async def admin_reorder_images(
    car_id: int,
    order: list[int],
    user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    car = await car_service.get_car(db, car_id)
    if not car:
        raise HTTPException(status_code=404)
    images = (
        await db.execute(select(CarImage).where(CarImage.car_id == car_id))
    ).scalars().all()
    by_id = {img.id: img for img in images}
    for sort_order, image_id in enumerate(order):
        if image_id in by_id:
            by_id[image_id].sort_order = sort_order
    await db.flush()
    await car_service.refresh_images_cache(db, car)
    await db.commit()
    await invalidate_cars_cache()
    return {"ok": True}


@admin_router.delete("/images/{image_id}")
async def admin_delete_image(
    image_id: int,
    user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    img = (await db.execute(select(CarImage).where(CarImage.id == image_id))).scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404)
    car_id = img.car_id
    await media.cars_storage.delete(img.image_path)
    await db.delete(img)
    await db.flush()
    car = await car_service.get_car(db, car_id)
    if car:
        await car_service.refresh_images_cache(db, car)
    await db.commit()
    await invalidate_cars_cache()
    return {"ok": True}

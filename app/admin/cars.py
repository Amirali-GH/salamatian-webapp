from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin._deps import admin_user_or_redirect
from app.core.cache import invalidate_cars_cache
from app.database import get_db
from app.models import Car, CarImage, CarSource, CarStatus, User, UserRole
from app.schemas.car import CarCreate, CarFilters, CarUpdate
from app.services import car_service, media

router = APIRouter(prefix="/admin/cars", tags=["admin"], include_in_schema=False)


def _can_edit(user: User) -> bool:
    return user.role in (UserRole.admin, UserRole.operator)


@router.get("")
async def list_cars_page(
    request: Request,
    brand: str | None = None,
    model: str | None = None,
    year: int | None = None,
    car_status: str | None = None,
    location: str | None = None,
    limit: int = 25,
    offset: int = 0,
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    filters = CarFilters(
        brand=brand,
        model=model,
        year_min=year,
        year_max=year,
        location=location,
        status=CarStatus(car_status) if car_status else None,
        limit=limit,
        offset=offset,
    )
    items, total = await car_service.list_cars(db, filters)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "admin/cars_list.html",
        {
            "request": request,
            "user": user_or_redirect,
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "filters": filters,
            "statuses": [s.value for s in CarStatus],
        },
    )


@router.get("/new")
async def new_car_form(request: Request, user_or_redirect=Depends(admin_user_or_redirect)):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    if not _can_edit(user_or_redirect):
        raise HTTPException(status_code=403, detail="Forbidden")
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "admin/car_form.html",
        {"request": request, "user": user_or_redirect, "car": None, "images": []},
    )


@router.post("/new")
async def new_car_submit(
    request: Request,
    brand: str = Form(...),
    model: str = Form(...),
    year: int = Form(...),
    price: str = Form(...),
    mileage: int | None = Form(None),
    gearbox: str | None = Form(None),
    fuel_type: str | None = Form(None),
    color: str | None = Form(None),
    location: str | None = Form(None),
    description: str | None = Form(None),
    car_status: str = Form("draft"),
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    if not _can_edit(user_or_redirect):
        raise HTTPException(status_code=403)
    try:
        price_dec = Decimal(price)
    except InvalidOperation:
        raise HTTPException(status_code=400, detail="Invalid price")
    payload = CarCreate(
        brand=brand,
        model=model,
        year=year,
        price=price_dec,
        mileage=mileage,
        gearbox=gearbox or None,
        fuel_type=fuel_type or None,
        color=color,
        location=location,
        description=description,
        status=CarStatus(car_status),
        source=CarSource.manual,
    )
    car = await car_service.create_car(db, payload, user_or_redirect.id)
    await db.commit()
    await invalidate_cars_cache()
    return RedirectResponse(url=f"/admin/cars/{car.id}/edit", status_code=303)


@router.get("/{car_id}/edit")
async def edit_car_form(
    request: Request,
    car_id: int,
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    car = await car_service.get_car(db, car_id)
    if not car:
        raise HTTPException(status_code=404)
    templates = request.app.state.templates
    await car.awaitable_attrs.images  # ensure loaded
    return templates.TemplateResponse(
        "admin/car_form.html",
        {
            "request": request,
            "user": user_or_redirect,
            "car": car,
            "images": car.images,
        },
    )


@router.post("/{car_id}/edit")
async def edit_car_submit(
    request: Request,
    car_id: int,
    brand: str = Form(...),
    model: str = Form(...),
    year: int = Form(...),
    price: str = Form(...),
    mileage: int | None = Form(None),
    gearbox: str | None = Form(None),
    fuel_type: str | None = Form(None),
    color: str | None = Form(None),
    location: str | None = Form(None),
    description: str | None = Form(None),
    car_status: str = Form("draft"),
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    if not _can_edit(user_or_redirect):
        raise HTTPException(status_code=403)
    car = await car_service.get_car(db, car_id)
    if not car:
        raise HTTPException(status_code=404)
    try:
        price_dec = Decimal(price)
    except InvalidOperation:
        raise HTTPException(status_code=400, detail="Invalid price")
    payload = CarUpdate(
        brand=brand,
        model=model,
        year=year,
        price=price_dec,
        mileage=mileage,
        gearbox=gearbox or None,
        fuel_type=fuel_type or None,
        color=color,
        location=location,
        description=description,
        status=CarStatus(car_status),
    )
    await car_service.update_car(db, car, payload, user_or_redirect.id)
    await db.commit()
    await invalidate_cars_cache()
    return RedirectResponse(url=f"/admin/cars/{car.id}/edit", status_code=303)


@router.post("/{car_id}/publish")
async def publish_car_action(
    car_id: int,
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    if not _can_edit(user_or_redirect):
        raise HTTPException(status_code=403)
    car = await car_service.get_car(db, car_id)
    if not car:
        raise HTTPException(status_code=404)
    await car_service.publish_car(db, car, user_or_redirect.id)
    await db.commit()
    await invalidate_cars_cache()
    return RedirectResponse(url="/admin/cars", status_code=303)


@router.post("/{car_id}/archive")
async def archive_car_action(
    car_id: int,
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    if not _can_edit(user_or_redirect):
        raise HTTPException(status_code=403)
    car = await car_service.get_car(db, car_id)
    if not car:
        raise HTTPException(status_code=404)
    await car_service.archive_car(db, car, user_or_redirect.id)
    await db.commit()
    await invalidate_cars_cache()
    return RedirectResponse(url="/admin/cars", status_code=303)


@router.post("/{car_id}/images")
async def upload_car_image(
    car_id: int,
    images: list[UploadFile],
    user_or_redirect=Depends(admin_user_or_redirect),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    if not _can_edit(user_or_redirect):
        raise HTTPException(status_code=403)
    car = await car_service.get_car(db, car_id)
    if not car:
        raise HTTPException(status_code=404)
    base_order = (car.images_json or [])
    start = len(base_order)
    for i, upload in enumerate(images):
        rel = await media.save_car_image(upload, car_id)
        db.add(CarImage(car_id=car_id, image_path=rel, sort_order=start + i))
    await db.flush()
    await car_service.refresh_images_cache(db, car)
    # Enqueue optimization
    from app.workers.tasks import image_optimize_task

    for img in car.images:
        image_optimize_task.delay(img.id)
    await db.commit()
    await invalidate_cars_cache()
    return RedirectResponse(url=f"/admin/cars/{car_id}/edit", status_code=303)

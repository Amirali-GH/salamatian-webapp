from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import car_service

router = APIRouter(tags=["public"], include_in_schema=False)


@router.get("/")
async def home(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse("public/index.html", {"request": request})


@router.get("/car/{car_id}")
async def car_detail(
    request: Request,
    car_id: int,
    db: AsyncSession = Depends(get_db),
):
    car = await car_service.get_public_car(db, car_id)
    if not car:
        raise HTTPException(status_code=404)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "public/car_popup.html",
        {
            "request": request,
            "car": car,
            "images": car.images_json or [],
            "title": f"{car.brand} {car.model} {car.year}",
        },
    )

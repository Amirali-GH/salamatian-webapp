from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import CarSource, CarStatus, FuelType, Gearbox


class CarImageOut(BaseModel):
    id: int
    image_path: str
    sort_order: int

    model_config = {"from_attributes": True}


class CarBase(BaseModel):
    brand: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=1900, le=2100)
    price: Decimal = Field(gt=0)
    mileage: int | None = Field(default=None, ge=0)
    gearbox: Gearbox | None = None
    fuel_type: FuelType | None = None
    color: str | None = Field(default=None, max_length=50)
    body_status: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=100)
    engine_volume: str | None = Field(default=None, max_length=50)
    engine_power: str | None = Field(default=None, max_length=50)
    acceleration: str | None = Field(default=None, max_length=50)
    fuel_consumption: str | None = Field(default=None, max_length=50)
    brake_system: str | None = Field(default=None, max_length=100)
    description: str | None = None
    features_json: dict | None = None


class CarCreate(CarBase):
    status: CarStatus = CarStatus.draft
    source: CarSource = CarSource.manual
    excel_row_id: str | None = None


class CarUpdate(BaseModel):
    brand: str | None = Field(default=None, min_length=1, max_length=100)
    model: str | None = Field(default=None, min_length=1, max_length=100)
    year: int | None = Field(default=None, ge=1900, le=2100)
    price: Decimal | None = Field(default=None, gt=0)
    mileage: int | None = Field(default=None, ge=0)
    gearbox: Gearbox | None = None
    fuel_type: FuelType | None = None
    color: str | None = None
    body_status: str | None = None
    location: str | None = None
    engine_volume: str | None = None
    engine_power: str | None = None
    acceleration: str | None = None
    fuel_consumption: str | None = None
    brake_system: str | None = None
    description: str | None = None
    features_json: dict | None = None
    status: CarStatus | None = None


class CarOut(CarBase):
    id: int
    status: CarStatus
    source: CarSource
    excel_row_id: str | None
    images_json: list | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CarListItem(BaseModel):
    id: int
    brand: str
    model: str
    year: int
    price: Decimal
    mileage: int | None
    gearbox: Gearbox | None
    fuel_type: FuelType | None
    location: str | None
    status: CarStatus
    images_json: list | None = None

    model_config = {"from_attributes": True}


class CarListResponse(BaseModel):
    items: list[CarListItem]
    total: int
    limit: int
    offset: int


class CarFilters(BaseModel):
    brand: str | None = None
    model: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    gearbox: Gearbox | None = None
    fuel_type: FuelType | None = None
    location: str | None = None
    search: str | None = None
    status: CarStatus | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort: str = Field(default="-created_at")

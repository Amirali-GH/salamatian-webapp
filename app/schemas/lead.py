from datetime import datetime

from pydantic import BaseModel, Field

from app.models import LeadStatus, LeadType


class LeadBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=4, max_length=32)
    car_brand: str | None = Field(default=None, max_length=100)
    car_model: str | None = Field(default=None, max_length=100)
    year: int | None = Field(default=None, ge=1900, le=2100)
    mileage: int | None = Field(default=None, ge=0)
    color: str | None = Field(default=None, max_length=50)
    description: str | None = None


class ConsultationLeadCreate(LeadBase):
    pass


class SellLeadCreate(LeadBase):
    pass


class LeadOut(LeadBase):
    id: int
    type: LeadType
    status: LeadStatus
    operator_note: str | None = None
    images_json: list | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadUpdate(BaseModel):
    status: LeadStatus | None = None
    operator_note: str | None = None


class LeadListResponse(BaseModel):
    items: list[LeadOut]
    total: int
    limit: int
    offset: int

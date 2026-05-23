from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TestCatalogData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    name_hindi: str | None
    description: str | None
    price: Decimal | None
    duration_hours: int
    requires_fasting: bool
    home_collection_available: bool
    category: str | None
    is_active: bool
    sort_order: int


class TestCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: TestCatalogData


class TestCatalogCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    name_hindi: str | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    duration_hours: int = Field(default=4, ge=1)
    requires_fasting: bool = False
    home_collection_available: bool = True
    category: str | None = None
    is_active: bool = True
    sort_order: int = 0


class TestCatalogUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    name_hindi: str | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    duration_hours: int | None = Field(default=None, ge=1)
    requires_fasting: bool | None = None
    home_collection_available: bool | None = None
    category: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None

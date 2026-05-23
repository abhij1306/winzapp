from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)
    request_id: str


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


class PaginationMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int
    page_size: int
    total: int


class PaginatedResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    data: list[T]
    pagination: PaginationMeta

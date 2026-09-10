from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    skip: int
    limit: int


class HealthResponse(BaseModel):
    status: str
    version: str
    checks: dict[str, str]


class SuccessResponse(BaseModel):
    message: str
    id: int | None = None

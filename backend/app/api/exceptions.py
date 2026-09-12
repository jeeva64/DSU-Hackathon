from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("backend.api")


class AppError(Exception):
    """Base application error."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str | int) -> None:
        super().__init__(
            status_code=404,
            code="NOT_FOUND",
            message=f"{resource} with ID {resource_id} not found.",
            details={"resource": resource, "resource_id": str(resource_id)},
        )


class ValidationError(AppError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            status_code=422,
            code="INVALID_INPUT",
            message=message,
            details=details,
        )


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            status_code=409,
            code="RESOURCE_CONFLICT",
            message=message,
        )


class DatabaseError(AppError):
    def __init__(self, message: str = "A database error occurred") -> None:
        super().__init__(
            status_code=500,
            code="DATABASE_ERROR",
            message=message,
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning("AppError: %s | path=%s", exc.code, request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(
                {"error": {"code": exc.code, "message": exc.message, "details": exc.details}}
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning("ValidationError | path=%s", request.url.path)
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": "Validation error",
                        "details": exc.errors(),
                    }
                }
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(
                {"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}}
            ),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Services raise ValueError for missing entities ("... not found").

        Those map to a useful 404 instead of an unhandled 500; other
        ValueErrors become a 422 with the message preserved. Request-body
        validation failures are handled earlier by RequestValidationError.
        """
        logger.warning("ValueError | path=%s | %s", request.url.path, exc)
        if "not found" in str(exc).lower():
            status_code, code = 404, "NOT_FOUND"
        else:
            status_code, code = 422, "INVALID_INPUT"
        return JSONResponse(
            status_code=status_code,
            content=jsonable_encoder(
                {"error": {"code": code, "message": str(exc)}}
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception | path=%s", request.url.path)
        return JSONResponse(
            status_code=500,
            content=jsonable_encoder(
                {
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "An unexpected error occurred.",
                    }
                }
            ),
        )

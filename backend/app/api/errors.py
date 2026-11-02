"""Canonical safe HTTP errors for the Phase 1 API."""
from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas import ErrorResponse


class APIProblem(Exception):
    def __init__(self, status_code: int, code: str, detail: str) -> None:
        self.status_code = status_code
        self.code = code
        self.detail = detail


def _request_id(request: Request) -> UUID:
    value = getattr(request.state, "request_id", None)
    if isinstance(value, UUID):
        return value
    value = uuid4()
    request.state.request_id = value
    return value


def _response(request: Request, status: int, code: str, detail: str) -> JSONResponse:
    request_id = _request_id(request)
    body = ErrorResponse(detail=detail, code=code, request_id=request_id)
    return JSONResponse(
        status_code=status,
        content=body.model_dump(mode="json"),
        headers={"X-Request-ID": str(request_id)},
    )


async def handle_api_problem(request: Request, exc: APIProblem) -> JSONResponse:
    return _response(request, exc.status_code, exc.code, exc.detail)


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _response(
        request, 422, "VALIDATION_ERROR", "The request does not match the API contract."
    )


async def handle_http_error(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    if exc.status_code == 404:
        return _response(request, 404, "NOT_FOUND", "The requested resource was not found.")
    if exc.status_code == 403:
        return _response(request, 403, "FORBIDDEN", "This action is not permitted.")
    if exc.status_code == 401:
        return _response(request, 401, "UNAUTHORIZED", "Authentication is required.")
    return _response(request, exc.status_code, "INTERNAL_ERROR", "The request could not be completed.")


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    return _response(request, 500, "INTERNAL_ERROR", "The request could not be completed.")

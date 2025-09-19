# samos/api/errors.py
from __future__ import annotations

from fastapi import Request, FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from samos.api.utils.http import new_request_id


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def on_request_validation_error(request: Request, exc: RequestValidationError):
        rid = new_request_id()
        details = {"errors": exc.errors()}
        body = {
            "ok": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": details,
            },
            "request_id": rid,
        }
        return JSONResponse(status_code=422, content=body)

    @app.exception_handler(StarletteHTTPException)
    async def on_http_exception(request: Request, exc: StarletteHTTPException):
        rid = new_request_id()
        code = "HTTP_ERROR"
        if exc.status_code == 404:
            code = "NOT_FOUND"
        elif exc.status_code == 403:
            code = "FORBIDDEN"
        body = {
            "ok": False,
            "error": {
                "code": code,
                "message": str(exc.detail) if exc.detail else "HTTP error",
                "details": None,
            },
            "request_id": rid,
        }
        return JSONResponse(status_code=exc.status_code, content=body)

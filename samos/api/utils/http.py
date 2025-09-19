# samos/api/utils/http.py
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from samos.api.schemas import ErrorEnvelope, ErrorObject, ListEnvelope, OkEnvelope


# ---- request id helpers ------------------------------------------------------
REQUEST_ID_HEADER = "x-request-id"

def new_request_id() -> str:
    return str(uuid4())

def get_request_id(request: Optional[Request]) -> str:
    if request is None:
        return new_request_id()
    rid = request.headers.get(REQUEST_ID_HEADER)
    return rid if rid else new_request_id()


# ---- helpers -----------------------------------------------------------------
def _to_jsonable(item: Any) -> Any:
    """
    Ensure Pydantic models (and nested datetimes) are converted to JSON-safe
    structures. For BaseModel we use model_dump(mode='json').
    """
    if isinstance(item, BaseModel):
        return item.model_dump(mode="json")
    return item


# ---- success envelopes -------------------------------------------------------
def ok(
    data: Any,
    status_code: int = 200,
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    payload = OkEnvelope(ok=True, data=_to_jsonable(data)).model_dump(mode="json")
    return JSONResponse(content=payload, status_code=status_code, headers=headers)


def ok_list(
    items: Iterable[Any],
    next_cursor: Optional[str] = None,
    status_code: int = 200,
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    json_items = [_to_jsonable(x) for x in items]
    env = ListEnvelope(ok=True, data=json_items, next_cursor=next_cursor)
    return JSONResponse(content=env.model_dump(mode="json"), status_code=status_code, headers=headers)


# ---- error envelopes ---------------------------------------------------------
def fail(
    code: str,
    message: str,
    *,
    request: Optional[Request] = None,
    details: Optional[Dict[str, Any]] = None,
    status_code: int = 400,
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    rid = get_request_id(request)
    err = ErrorEnvelope(
        ok=False,
        error=ErrorObject(code=code, message=message, details=details),
        request_id=rid,
    )
    hdrs = {REQUEST_ID_HEADER: rid}
    if headers:
        hdrs.update(headers)
    return JSONResponse(content=err.model_dump(mode="json"), status_code=status_code, headers=hdrs)

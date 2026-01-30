from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi.responses import JSONResponse


def _ok(label: str, data: Optional[Dict[str, Any]] = None, status_code: int = 200) -> JSONResponse:
    """
    Standard success envelope used across SamOS routes.
    """
    if data is None:
        data = {}
    payload = {"ok": True, "label": label, "data": data}
    return JSONResponse(status_code=status_code, content=payload)


def _err(msg: str, *, status_code: int = 404, label: str = "error", **extra: Any) -> JSONResponse:
    """
    Standard error envelope used across SamOS routes.
    Keeps your existing pattern: {"detail": {...}} for errors.
    """
    error: Dict[str, Any] = {"msg": msg}
    if extra:
        error.update(extra)

    payload = {"ok": False, "label": label, "error": error}
    return JSONResponse(status_code=status_code, content={"detail": payload})


def _detail(msg: str, *, status_code: int = 400, **extra: Any) -> JSONResponse:
    """
    Convenience variant if some routes prefer {"detail": "..."}.
    """
    detail: Dict[str, Any] = {"msg": msg}
    if extra:
        detail.update(extra)
    return JSONResponse(status_code=status_code, content={"detail": detail})

def ok_list(label: str, items: list, *, status_code: int = 200, **extra: Any) -> JSONResponse:
    """
    Success envelope for list responses.
    Payload format matches _ok: {"ok": True, "label": ..., "data": {...}}
    """
    data: Dict[str, Any] = {"count": len(items), "items": items}
    if extra:
        data.update(extra)
    return _ok(label, data=data, status_code=status_code)

def fail(msg: str, *, status_code: int = 400, label: str = "error", **extra: Any) -> JSONResponse:
    """
    Alias used by some routers. Keeps error envelope consistent with _err.
    """
    return _err(msg, status_code=status_code, label=label, **extra)

"""
samos.api.main

Deterministic app wiring:
- Do NOT rely on optional "Central SamRouter" (it has been failing due to helper import issues).
- Always include Ops router (routes_ops) so /ops/* endpoints are stable.
- Include other routers only if their imports succeed.
"""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Optional

from fastapi import FastAPI
from sqlalchemy import text

# IMPORTANT: SessionLocal must come from your real DB module.
# If this import fails, readyz will return db error, but the API can still start.
try:
    from samos.api.db import SessionLocal  # type: ignore
except Exception:  # pragma: no cover
    SessionLocal = None  # type: ignore

log = logging.getLogger("samos")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="SamOS API")


def _try_include(module_path: str, attr: str = "router", prefix: str = "") -> bool:
    """
    Try importing module_path and include its APIRouter named `attr`.
    Returns True if included, False otherwise.
    """
    try:
        mod = import_module(module_path)
        router = getattr(mod, attr)
        app.include_router(router, prefix=prefix)
        log.info("[SamOS] Included router: %s.%s%s", module_path, attr, f" (prefix='{prefix}')" if prefix else "")
        return True
    except Exception as e:
        log.warning("[SamOS] Failed to include router: %s.%s (%s: %s)", module_path, attr, type(e).__name__, e)
        return False


# -------------------------------------------------------------------
# ROUTER WIRING (ORDER MATTERS)
# -------------------------------------------------------------------
# 1) OPS MUST ALWAYS BE PRESENT
# routes_ops.py already defines prefix="/ops" on its router, so DO NOT add prefix here.
_try_include("samos.api.routes_ops", "router")

# 2) CORE ROUTERS (best-effort; include if present)
_try_include("samos.api.routes_sessions", "router")
_try_include("samos.api.routes_images", "router")
_try_include("samos.api.routes_chat", "router")

# 3) OPTIONAL FEATURE SETS (best-effort)
_try_include("samos.api.routes_alpha", "router")
_try_include("samos.api.routes_admin", "router")

# If routes_events currently fails due to helper imports (ok_list/_ok_list), keep it best-effort.
_try_include("samos.api.routes_events", "router")

# Snapshot/health modules have been failing in your logs; keep best-effort.


# -------------------------------------------------------------------
# HEALTH ENDPOINTS (always available)
# -------------------------------------------------------------------
@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "service": "samos"}

@app.get("/health")
def health() -> dict:
    return healthz()

@app.get("/readyz")
def readyz() -> dict:
    """
    DB readiness check. If SessionLocal import fails, report that clearly.
    """
    if SessionLocal is None:
        return {"ok": False, "db": "SessionLocal import failed (check samos.api.db import path)"}

    try:
        with SessionLocal() as s:  # type: ignore
            s.execute(text("SELECT 1"))
        return {"ok": True, "db": "ready"}
    except Exception as e:
        return {"ok": False, "db": f"error: {type(e).__name__}"}

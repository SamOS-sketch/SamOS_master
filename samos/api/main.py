# samos/api/main.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure storage exists (outputs/ by default, or SAM_STORAGE_DIR)
from samos.api.paths import ensure_static_dirs

# DB: guarantee schema on startup
from samos.api.db import Base, SessionLocal

# Canonical routers (must exist)
from samos.api.routes_images import router as images_router
from samos.api.routes_sessions import router as sessions_router

# Optional routers (best-effort import; ok if absent)
def _try_include(app: FastAPI, import_path: str, attr: str) -> None:
    try:
        mod = __import__(import_path, fromlist=[attr])
        router = getattr(mod, attr)
        app.include_router(router)
    except Exception:
        # Keep server booting even if optional routers are missing
        pass


# -------------------- App --------------------
ensure_static_dirs()

app = FastAPI(
    title="SamOS API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Dev-friendly CORS (tighten later if you expose this)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure DB schema exists at startup (creates missing tables; safe to run repeatedly)
@app.on_event("startup")
def _ensure_schema() -> None:
    try:
        with SessionLocal() as s:
            bind = s.get_bind()
            Base.metadata.create_all(bind=bind)
    except Exception:
        # Don't block startup if DB is read-only or unavailable; routes will surface errors.
        pass

# Required routers
app.include_router(sessions_router)
app.include_router(images_router)

# Optional routers (only if present)
_try_include(app, "samos.api.routes_events", "router")
_try_include(app, "samos.api.routes_admin", "router")
_try_include(app, "samos.api.routes_snapshot", "router")
_try_include(app, "samos.api.health", "router")

# Basic liveness
@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "service": "samos", "version": "1.0.0"}

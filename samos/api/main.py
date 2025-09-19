# samos/api/main.py
from __future__ import annotations

import os
from typing import Generator, List, Optional
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ---- Local imports ----------------------------------------------------------
from samos.api.paths import ensure_static_dirs
from samos.api.db import SessionLocal  # removed: init as init_db
from samos.api.routes_images import router as images_router
# from samos.api.routes_metrics import router as metrics_router  # optional

# ---- Lifespan: startup/shutdown --------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    App lifecycle manager.
    - Ensures STATIC_DIR structure exists (images/, tmp/refs, tmp/work)
    """
    static_base = ensure_static_dirs()
    print(f"[Startup] Static base directory: {static_base}")
    yield
    # (Optional) Add shutdown tasks here if needed.

# ---- App --------------------------------------------------------------------

app = FastAPI(
    title="SamOS API",
    version=os.getenv("SAMOS_API_VERSION", "0.12"),
    docs_url=os.getenv("DOCS_URL", "/docs"),
    redoc_url=os.getenv("REDOC_URL", "/redoc"),
    lifespan=lifespan,
)

# ---- CORS -------------------------------------------------------------------

def _parse_origins(val: Optional[str]) -> List[str]:
    """
    Parse CORS origins from env like:
      CORS_ORIGINS="http://localhost:3000,https://studio.apis"
    Fallback: allow localhost & 127.0.0.1 for dev convenience.
    """
    if not val:
        return [
            "http://localhost",
            "http://localhost:3000",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
        ]
    parts = [p.strip() for p in val.split(",") if p.strip()]
    return parts or ["http://localhost:3000"]

CORS_ORIGINS = _parse_origins(os.getenv("CORS_ORIGINS"))
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
CORS_ALLOW_METHODS = os.getenv("CORS_ALLOW_METHODS", "GET,POST,PUT,DELETE,OPTIONS")
CORS_ALLOW_HEADERS = os.getenv("CORS_ALLOW_HEADERS", "*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=[m.strip() for m in CORS_ALLOW_METHODS.split(",")],
    allow_headers=[h.strip() for h in CORS_ALLOW_HEADERS.split(",")],
)

# ---- DB dependency ----------------------------------------------------------

def get_db() -> Generator:
    """
    Standard SQLAlchemy session dependency.
    Usage in routes:
        db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---- Health endpoints -------------------------------------------------------

@app.get("/healthz")
async def healthz():
    """Liveness probe: returns 200 if the app process is alive."""
    return {"status": "ok"}

@app.get("/readyz")
async def readyz():
    """Readiness probe: app is up; DB connectivity is best-effort checked by routes using get_db."""
    return {"ready": True}

@app.get("/")
async def root():
    """Simple root to confirm service identity and configured static base (for debugging)."""
    return {
        "name": "SamOS API",
        "version": os.getenv("SAMOS_API_VERSION", "0.12"),
        "static_dir": str(ensure_static_dirs()),
    }

# ---- Routers ----------------------------------------------------------------

# Image routes (Phase 11 + 12 work continues here)
app.include_router(images_router, prefix="", tags=["images"])

# Optional metrics router
# app.include_router(metrics_router, prefix="", tags=["metrics"])


from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from samos.api.db import (
    EMM as DBEMM,
    Event as DBEvent,
    Image as DBImage,
    Memory as DBMemory,
    Session as DBSession,
    SessionLocal,
    init_db,
)
from samos.api.image.stub import StubProvider
from samos.api.models import (
    EMMCreateRequest,
    EMMItem,
    EMMListResponse,
    ImageGenerateRequest,
    ImageGenerateResponse,  # Remove this line
)
from samos.api.obs.events import record_event
from samos.api.routes_images import router as image_router
from samos.api.routes_snapshot import router as snapshot_router
from samos.config import assert_persona_safety, settings
from samos.core.memory_agent import get_memory_agent
from samos.core.soulprint_loader import load_soulprint

# ----------------------------------------------------------------------------- 
# App & middleware 
# ----------------------------------------------------------------------------- 

app = FastAPI(title="SamOS API (Phase 11.1)")

# CORS from settings (comma-separated list already parsed in settings.cors_origins)
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Mount routers
app.include_router(snapshot_router)
app.include_router(image_router)

# In-memory counters
_METRICS: Counter[str] = Counter()

# Globals filled during startup
SOULPRINT: dict | object = {}
SOULPRINT_PATH: str = "UNAVAILABLE"
AGENT = None  # MemoryAgent

# ----------------------------------------------------------------------------- 
# Providers (feature-flagged; lazy import to avoid optional deps at import time) 
# ----------------------------------------------------------------------------- 

class _ComfyUIStub(StubProvider):
    """Placeholder so IMAGE_PROVIDER=comfyui still works on machines without ComfyUI."""
    name = "comfyui-stub"


def _make_openai_provider():
    from samos.api.image.openai_provider import OpenAIProvider
    return OpenAIProvider()


_PROVIDER_FACTORIES: dict[str, Callable[[], object]] = {
    "stub": lambda: StubProvider(),
    "openai": _make_openai_provider,
    "comfyui": lambda: _ComfyUIStub(),
}
_PROVIDER_CACHE: dict[str, object] = {}


def _get_provider():
    name = (settings.IMAGE_PROVIDER or "stub").lower()
    factory = _PROVIDER_FACTORIES.get(name)
    if not factory:
        raise HTTPException(status_code=500, detail=f"Unknown IMAGE_PROVIDER: {name}")
    if name not in _PROVIDER_CACHE:
        _PROVIDER_CACHE[name] = factory()
    return _PROVIDER_CACHE[name]


def _reference_image(default_fallback: str = "ref_alpha.jpg") -> str:
    # Keep env override for backward-compat
    return os.getenv("REFERENCE_IMAGE_ALPHA", "") or default_fallback


# ----------------------------------------------------------------------------- 
# Startup: persona safety → DB init → soulprint → agent 
# ----------------------------------------------------------------------------- 

@app.on_event("startup")
async def _startup() -> None:
    global SOULPRINT, SOULPRINT_PATH, AGENT

    # Persona guard (reads env/settings and can raise)
    assert_persona_safety()

    # DB init (prefer URL argument; fall back to env for older init_db)
    db_url = settings.resolved_db_url()
    try:
        init_db(db_url)  # type: ignore[call-arg]  # tolerate older init_db signature
    except TypeError:
        os.environ["DB_URL"] = db_url
        init_db()

    # Soulprint (path & parsed object)
    try:
        SOULPRINT, SOULPRINT_PATH = load_soulprint()
        print(f"[SamOS] Soulprint: {SOULPRINT_PATH}")
    except Exception as e:  # noqa: BLE001
        SOULPRINT, SOULPRINT_PATH = {}, "UNAVAILABLE"
        print(f"[SamOS] Soulprint load error: {e}")

    # Memory agent (optional)
    try:
        AGENT = get_memory_agent()
    except Exception as e:  # noqa: BLE001
        AGENT = None
        print(f"[SamOS] MemoryAgent init error: {e}")


# ----------------------------------------------------------------------------- 
# Helpers 
# ----------------------------------------------------------------------------- 

DEFAULT_MODE = os.getenv("SAM_MODE_DEFAULT", "work")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _bucket_start(dt: datetime, period: str) -> datetime:
    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    if period == "hour":
        return dt.replace(minute=0, second=0, microsecond=0)
    if period == "day":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    raise ValueError("period must be 'hour' or 'day'")


def _bump_bucket(metric: str, period: str, ts: datetime, inc: int = 1) -> None:
    bs = _bucket_start(ts, period)
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT id FROM metrics_buckets "
                "WHERE metric = :m AND period = :p AND bucket_start = :bs"
            ),
            {"m": metric, "p": period, "bs": bs},
        ).fetchone()
        if row:
            db.execute(
                text("UPDATE metrics_buckets SET value = value + :inc WHERE id = :id"),
                {"inc": inc, "id": row[0]},
            )
        else:
            db.execute(
                text(
                    "INSERT INTO metrics_buckets (metric, period, bucket_start, value) "
                    "VALUES (:m, :p, :bs, :v)"
                ),
                {"m": metric, "p": period, "bs": bs, "v": inc},
            )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    finally:
        db.close()


def _bump_buckets(metric: str, ts: datetime, inc: int = 1) -> None:
    _bump_bucket(metric, "hour", ts, inc)
    _bump_bucket(metric, "day", ts, inc)


def _parse_iso(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    return datetime.fromisoformat(dt.rstrip("Z"))


# ----------------------------------------------------------------------------- 
# Health & metrics 
# ----------------------------------------------------------------------------- 

@app.get("/health")
def health():
    sp_name = SOULPRINT.get("name") if isinstance(SOULPRINT, dict) else None
    return {
        "status": "ok",
        "provider": settings.IMAGE_PROVIDER,
        "soulprint_path": Path(SOULPRINT_PATH).name if SOULPRINT_PATH else "UNAVAILABLE",
        "soulprint_name": sp_name
        or ("SamOS Demo" if settings.SAMOS_PERSONA == "demo" else "SamOS Private"),
    }


@app.get("/metrics")
def metrics():
    return dict(_METRICS)


@app.post("/metrics/reset")
def metrics_reset(also_buckets: bool = False, also_counters_table: bool = True):
    before = dict(_METRICS)
    _METRICS.clear()
    deleted_buckets = 0
    deleted_counters = 0
    if also_buckets or also_counters_table:
        db = SessionLocal()
        try:
            if also_buckets:
                res = db.execute(text("DELETE FROM metrics_buckets"))
                deleted_buckets = getattr(res, "rowcount", 0)
            if also_counters_table:
                res2 = db.execute(text("DELETE FROM metrics_counters"))
                deleted_counters = getattr(res2, "rowcount", 0)
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        finally:
            db.close()

    try:
        record_event(
            "metrics.reset",
            "Metrics counters reset",
            None,
            {
                "also_buckets": also_buckets,
                "also_counters_table": also_counters_table,
                "deleted_buckets": deleted_buckets,
                "deleted_counters": deleted_counters,
                "before": before,
            },
        )
    except Exception:  # noqa: BLE001
        pass

    return {
        "ok": True,
        "cleared_in_memory": True,
        "also_buckets": also_buckets,
        "also_counters_table": also_counters_table,
        "deleted_buckets": deleted_buckets,
        "deleted_counters": deleted_counters,
        "before": before,
        "after": dict(_METRICS),
    }


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    ts = _utc_now()
    _METRICS["http.requests"] += 1
    _METRICS[f"http.path:{request.url.path}"] += 1
    _bump_buckets("http.requests", ts)
    _bump_buckets(f"http.path:{request.url.path}", ts)
    return await call_next(request)


# ----------------------------------------------------------------------------- 
# Events 
# ----------------------------------------------------------------------------- 

@app.get("/events")
def list_events(
    session_id: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
    limit: int = Query(200, gt=1, le=1000),
):
    db = SessionLocal()
    try:
        q = db.query(DBEvent)
        if session_id:
            q = q.filter(DBEvent.session_id == session_id)
        if kind:
            q = q.filter(DBEvent.kind == kind)
        sdt = _parse_iso(since)
        edt = _parse_iso(until)
        if sdt:
            q = q.filter(DBEvent.ts >= sdt)
        if edt:
            q = q.filter(DBEvent.ts <= edt)
        rows = q.order_by(DBEvent.id.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "ts": r.ts.isoformat() if r.ts else None,
                "session_id": r.session_id,
                "kind": r.kind,
                "message": r.message,
                "meta": json.loads(r.meta_json or "{}"),
            }
            for r in rows
        ]
    finally:
        db.close()


@app.get("/events/export")
def export_events(
    session_id: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
    limit: int = Query(1000, gt=1, le=2000),
):
    return list_events(session_id=session_id, kind=kind, since=since, until=until, limit=limit)


# ----------------------------------------------------------------------------- 
# Sessions 
# ----------------------------------------------------------------------------- 

@app.post("/session/start", response_model=SessionStartResponse)
def start_session():
    db = SessionLocal()
    try:
        sid = str(uuid4())
        sess = DBSession(id=sid, mode=DEFAULT_MODE)
        db.add(sess)
        db.commit()

        record_event("session.start", "Session created", sid, {"mode": sess.mode})
        try:
            if AGENT:
                AGENT.on_session_start(sid, sess.mode)
                AGENT.on_event(sid, "session.start", "Session created", {"mode": sess.mode})
        except Exception:  # noqa: BLE001
            pass

        return SessionStartResponse(session_id=sid, mode=sess.mode)
    finally:
        db.close()


@app.get("/session/mode", response_model=ModeGetResponse)
def get_mode(session_id: str = Query(...)):
    db = SessionLocal()
    try:
        sess = db.query(DBSession).filter(DBSession.id == session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        return ModeGetResponse(session_id=session_id, mode=sess.mode)
    finally:
        db.close()


@app.post("/session/mode", response_model=ModeGetResponse)
def set_mode(req: ModeSetRequest):
    db = SessionLocal()
    try:
        sess = db.query(DBSession).filter(DBSession.id == req.session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        sess.mode = req.mode
        db.add(sess)
        db.commit()

        record_event("mode.set", "Mode set", req.session_id, {"mode": sess.mode})
        try:
            if AGENT:
                AGENT.on_event(req.session_id, "mode.set", "Mode set", {"mode": sess.mode})
        except Exception:  # noqa: BLE001
            pass

        return ModeGetResponse(session_id=req.session_id, mode=sess.mode)
    finally:
        db.close()

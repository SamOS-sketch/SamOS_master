# samos/api/main.py
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from samos.api.db import (
    EMM as DBEMM,
)
from samos.api.db import (
    Event as DBEvent,
)
from samos.api.db import (
    Image as DBImage,
)
from samos.api.db import (
    Memory as DBMemory,
)
from samos.api.db import (
    Session as DBSession,
)
from samos.api.db import (
    SessionLocal,
    init_db,
)
from samos.api.image.stub import StubProvider

# --- App models/db/providers/routes (existing imports) ---
from samos.api.models import (
    EMMCreateRequest,
    EMMItem,
    EMMListResponse,
    ImageGenerateRequest,
    ImageGenerateResponse,
    MemoryItem,
    MemoryListResponse,
    MemoryPutRequest,
    ModeGetResponse,
    ModeSetRequest,
    SessionStartResponse,
)
from samos.api.obs.events import record_event
from samos.api.routes_images import router as image_router
from samos.api.routes_snapshot import router as snapshot_router

# --- SamOS config / safety ---
from samos.config import assert_persona_safety, settings
from samos.core.memory_agent import get_memory_agent
from samos.core.soulprint_loader import load_soulprint

# --------------------------
# App & middleware
# --------------------------

app = FastAPI(title="SamOS API (Phase 11 RC1)")

# CORS: default to same-origin; allow comma-separated overrides via env
allow_origins = settings.cors_origins or []
if allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Routes
app.include_router(snapshot_router)
app.include_router(image_router)

# In-memory metrics
_METRICS = Counter()

# Globals filled on startup
SOULPRINT: dict | object = {}
SOULPRINT_PATH: str = "UNAVAILABLE"
AGENT = None  # MemoryAgent instance


# --------------------------
# Providers (feature-flagged)
# --------------------------

def _make_openai_provider():
    from samos.api.image.openai_provider import OpenAIProvider
    return OpenAIProvider()

class _ComfyUIStub(StubProvider):
    """Placeholder so IMAGE_PROVIDER=comfyui still works on CPU machines."""
    name = "comfyui-stub"

_PROVIDER_FACTORIES = {
    "stub": lambda: StubProvider(),
    "openai": _make_openai_provider,
    "comfyui": lambda: _ComfyUIStub(),
}
_PROVIDER_CACHE: dict[str, object] = {}

def get_provider():
    name = settings.IMAGE_PROVIDER.lower()
    factory = _PROVIDER_FACTORIES.get(name)
    if not factory:
        raise HTTPException(status_code=500, detail=f"Unknown IMAGE_PROVIDER: {name}")
    if name not in _PROVIDER_CACHE:
        _PROVIDER_CACHE[name] = factory()
    return _PROVIDER_CACHE[name]

def get_reference_image(default_fallback: str = "ref_alpha.jpg") -> str:
    return os.getenv("REFERENCE_IMAGE_ALPHA", default_fallback)


# --------------------------
# Startup: DB + Soulprint + Agent, with safety guard
# --------------------------

@app.on_event("startup")
async def _startup():
    global SOULPRINT, SOULPRINT_PATH, AGENT

    # Enforce persona safety before touching anything sensitive
    assert_persona_safety()

    # Init DB with persona-aware URL
    db_url = settings.resolved_db_url()
    try:
        init_db(db_url)         # preferred if your init_db accepts a URL
    except TypeError:
        os.environ["DB_URL"] = db_url  # fallback: some versions read from env
        init_db()

    # Load soulprint (your loader already resolves persona/env internally)
    try:
        SOULPRINT, SOULPRINT_PATH = load_soulprint()
        print(f"[SamOS] Soulprint: {SOULPRINT_PATH}")
    except Exception as e:
        SOULPRINT, SOULPRINT_PATH = {}, "UNAVAILABLE"
        print(f"[SamOS] Soulprint load error: {e}")

    # MemoryAgent
    try:
        AGENT = get_memory_agent()
    except Exception as e:
        AGENT = None
        print(f"[SamOS] MemoryAgent init error: {e}")


# --------------------------
# Helpers
# --------------------------

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
            text("SELECT id FROM metrics_buckets WHERE metric=:m AND period=:p AND bucket_start=:bs"),
            {"m": metric, "p": period, "bs": bs},
        ).fetchone()
        if row:
            db.execute(text("UPDATE metrics_buckets SET value = value + :inc WHERE id=:id"),
                       {"inc": inc, "id": row[0]})
        else:
            db.execute(text(
                "INSERT INTO metrics_buckets (metric, period, bucket_start, value) VALUES (:m,:p,:bs,:v)"
            ), {"m": metric, "p": period, "bs": bs, "v": inc})
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

def _bump_buckets(metric: str, ts: datetime, inc: int = 1) -> None:
    _bump_bucket(metric, "hour", ts, inc)
    _bump_bucket(metric, "day", ts, inc)


# --------------------------
# Health & Metrics
# --------------------------

@app.get("/health")
def health():
    sp_name = None
    if isinstance(SOULPRINT, dict):
        sp_name = SOULPRINT.get("name")
    return {
        "status": "ok",
        "provider": settings.IMAGE_PROVIDER,
        "soulprint_path": Path(SOULPRINT_PATH).name if SOULPRINT_PATH else "UNAVAILABLE",
        "soulprint_name": sp_name or ("SamOS Demo" if settings.SAMOS_PERSONA == "demo" else "SamOS Private"),
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
                res = db.execute(text("DELETE FROM metrics_buckets")); deleted_buckets = getattr(res, "rowcount", 0)
            if also_counters_table:
                res2 = db.execute(text("DELETE FROM metrics_counters")); deleted_counters = getattr(res2, "rowcount", 0)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
    try:
        record_event("metrics.reset", "Metrics counters reset", None, {
            "also_buckets": also_buckets, "also_counters_table": also_counters_table,
            "deleted_buckets": deleted_buckets, "deleted_counters": deleted_counters, "before": before,
        })
    except Exception:
        pass
    return {"ok": True, "cleared_in_memory": True, "also_buckets": also_buckets,
            "also_counters_table": also_counters_table, "deleted_buckets": deleted_buckets,
            "deleted_counters": deleted_counters, "before": before, "after": dict(_METRICS)}


# ---- Request counter middleware ----
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    ts = _utc_now()
    _METRICS["http.requests"] += 1
    _METRICS[f"http.path:{request.url.path}"] += 1
    _bump_buckets("http.requests", ts)
    _bump_buckets(f"http.path:{request.url.path}", ts)
    return await call_next(request)


# --------------------------
# Events
# --------------------------

def _parse_iso(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    return datetime.fromisoformat(dt.rstrip("Z"))

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
        sdt = _parse_iso(since); edt = _parse_iso(until)
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


# --------------------------
# Sessions
# --------------------------

@app.post("/session/start", response_model=SessionStartResponse)
def start_session():
    db = SessionLocal()
    try:
        sid = str(uuid4())
        sess = DBSession(id=sid, mode=DEFAULT_MODE)
        db.add(sess); db.commit()
        record_event("session.start", "Session created", sid, {"mode": sess.mode})
        try:
            if AGENT:
                AGENT.on_session_start(sid, sess.mode)
                AGENT.on_event(sid, "session.start", "Session created", {"mode": sess.mode})
        except Exception:
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
        sess.mode = req.mode; db.add(sess); db.commit()
        record_event("mode.set", "Mode set", req.session_id, {"mode": sess.mode})
        try:
            if AGENT:
                AGENT.on_event(req.session_id, "mode.set", "Mode set", {"mode": sess.mode})
        except Exception:
            pass
        return ModeGetResponse(session_id=req.session_id, mode=sess.mode)
    finally:
        db.close()


# --------------------------
# Memory
# --------------------------

@app.post("/memory")
def put_memory(req: MemoryPutRequest):
    db = SessionLocal()
    try:
        sess = db.query(DBSession).filter(DBSession.id == req.session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        item = (
            db.query(DBMemory)
            .filter(DBMemory.session_id == req.session_id, DBMemory.key == req.key)
            .first()
        )
        if not item:
            item = DBMemory(
                session_id=req.session_id,
                key=req.key,
                value=req.value,
                meta_json=json.dumps(req.meta or {}),
            )
        else:
            item.value = req.value; item.meta_json = json.dumps(req.meta or {})
        db.add(item); db.commit()
        record_event("memory.put", "Memory saved", req.session_id, {"key": req.key})
        try:
            if AGENT:
                AGENT.on_insight(req.session_id, req.key, req.value)
        except Exception:
            pass
        return {"ok": True}
    finally:
        db.close()

@app.get("/memory", response_model=MemoryItem)
def get_memory(session_id: str = Query(...), key: str = Query(...)):
    db = SessionLocal()
    try:
        item = (
            db.query(DBMemory)
            .filter(DBMemory.session_id == session_id, DBMemory.key == key)
            .first()
        )
        if not item:
            raise HTTPException(status_code=404, detail="Memory not found")
        return MemoryItem(
            key=item.key,
            value=item.value,
            meta=json.loads(item.meta_json or "{}"),
            created_at=item.created_at.isoformat() + "Z",
            updated_at=item.updated_at.isoformat() + "Z",
        )
    finally:
        db.close()

@app.get("/memory/list", response_model=MemoryListResponse)
def list_memory(session_id: str = Query(...)):
    db = SessionLocal()
    try:
        items = db.query(DBMemory).filter(DBMemory.session_id == session_id).all()
        return MemoryListResponse(
            items=[
                MemoryItem(
                    key=i.key,
                    value=i.value,
                    meta=json.loads(i.meta_json or "{}"),
                    created_at=i.created_at.isoformat() + "Z",
                    updated_at=i.updated_at.isoformat() + "Z",
                )
                for i in items
            ]
        )
    finally:
        db.close()


# --------------------------
# EMM
# --------------------------

@app.post("/emm")
def create_emm(req: EMMCreateRequest):
    db = SessionLocal()
    try:
        sess = db.query(DBSession).filter(DBSession.id == req.session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        e = DBEMM(
            session_id=req.session_id,
            type=req.type,
            message=req.message,
            meta_json=json.dumps(req.meta or {}),
        )
        db.add(e); db.commit()
        record_event("emm.create", "EMM created", req.session_id, {"type": req.type})
        try:
            if AGENT:
                AGENT.on_emm(req.session_id, req.type, req.message)
        except Exception:
            pass
        return {"ok": True, "id": e.id}
    finally:
        db.close()

@app.get("/emm/list", response_model=EMMListResponse)
def list_emms(session_id: str = Query(...), limit: int = Query(50)):
    db = SessionLocal()
    try:
        rows = (
            db.query(DBEMM)
            .filter(DBEMM.session_id == session_id)
            .order_by(DBEMM.id.desc())
            .limit(limit)
            .all()
        )
        return EMMListResponse(
            items=[
                EMMItem(
                    id=r.id,
                    type=r.type,
                    message=r.message,
                    meta=json.loads(r.meta_json or "{}"),
                    created_at=r.created_at.isoformat() + "Z",
                )
                for r in rows
            ]
        )
    finally:
        db.close()

@app.get("/emm/export", response_model=EMMListResponse)
def export_emms(session_id: str = Query(...)):
    db = SessionLocal()
    try:
        rows = (
            db.query(DBEMM)
            .filter(DBEMM.session_id == session_id)
            .order_by(DBEMM.id.asc())
            .all()
        )
        return EMMListResponse(
            items=[
                EMMItem(
                    id=r.id,
                    type=r.type,
                    message=r.message,
                    meta=json.loads(r.meta_json or "{}"),
                    created_at=r.created_at.isoformat() + "Z",
                )
                for r in rows
            ]
        )
    finally:
        db.close()


# --------------------------
# Images
# --------------------------

# ---- Images ----
@app.post("/image/generate", response_model=ImageGenerateResponse)
def generate_image(req: ImageGenerateRequest):
    db = SessionLocal()
    try:
        # validate session
        sess = db.query(DBSession).filter(DBSession.id == req.session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")

        provider = get_provider()
        reference = getattr(req, "reference_image", None) or get_reference_image()

        # ----- success path -----
        try:
            result = provider.generate(
                session_id=req.session_id,
                prompt=req.prompt,
                reference_image=reference,
            )

            img = DBImage(
                id=result["image_id"],
                session_id=req.session_id,
                prompt=req.prompt,
                provider=result["provider"],
                url=result["url"],
                reference_used=result["reference_used"],
                status=result.get("status", "ok"),
                meta_json=json.dumps(result.get("meta", {})),
            )
            db.add(img)
            db.commit()

            record_event(
                "image.generate.ok",
                "Image created",
                req.session_id,
                {"provider": result.get("provider"), "image_id": result.get("image_id")},
            )

            _METRICS["image.ok"] += 1
            ts = _utc_now()
            _bump_buckets("image.ok", ts)

            try:
                AGENT.on_event(
                    req.session_id,
                    "image.generate.ok",
                    "Image created",
                    {"provider": result.get("provider")},
                )
            except Exception:
                pass

            return ImageGenerateResponse(**result)

        # ----- failure path -----
        except Exception as e:
            emm = DBEMM(
                session_id=req.session_id,
                type="OneBounce",
                message=str(e),
                meta_json=json.dumps({"prompt": req.prompt}),
            )
            db.add(emm)
            db.commit()

            img = DBImage(
                id=str(uuid4()),
                session_id=req.session_id,
                prompt=req.prompt,
                provider=getattr(provider, "name", "unknown"),
                url="",
                reference_used=reference,
                status="failed",
                meta_json=json.dumps({"error": str(e)}),
            )
            db.add(img)
            db.commit()

            record_event(
                "image.generate.fail",
                "Image failed",
                req.session_id,
                {"error": str(e)},
            )

            _METRICS["image.fail"] += 1
            ts = _utc_now()
            _bump_buckets("image.fail", ts)

            try:
                AGENT.on_event(
                    req.session_id,
                    "image.generate.fail",
                    "Image failed",
                    {"error": str(e)},
                )
            except Exception:
                pass

            raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")

    finally:
        db.close()

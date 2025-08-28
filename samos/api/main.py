import os
import json
from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4
from collections import Counter

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel  # ok to keep even if unused
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=str(Path(__file__).resolve().parents[2] / ".env"))
from sqlalchemy import text  # NEW: for simple UPSERT-by-hand
from samos.api.routes_images import router as image_router
 
# ---- Package imports (so uvicorn can find modules) ----
from samos.api.models import (
    SessionStartResponse, ModeSetRequest, ModeGetResponse,
    MemoryPutRequest, MemoryItem, MemoryListResponse,
    EMMCreateRequest, EMMItem, EMMListResponse,
    ImageGenerateRequest, ImageGenerateResponse
)

from samos.api.db import (
    SessionLocal, init_db,
    Session as DBSession, Memory as DBMemory, EMM as DBEMM, Image as DBImage,
    Event as DBEvent,
)

from samos.api.image.stub import StubProvider
from samos.api.obs.events import record_event
from samos.api.routes_snapshot import router as snapshot_router

# ------------------------------------------------------

load_dotenv()

# Defaults
DEFAULT_MODE = os.getenv("SAM_MODE_DEFAULT", "work")

app = FastAPI(title="SamOS API (Phase 4/5/6/7/8)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(snapshot_router)    # Phase 7 snapshots
app.include_router(image_router)       # Phase 8 image + routing

# --- Minimal in-memory metrics ---
_METRICS = Counter()

init_db()

# -------- Provider registry (lazy) --------
def _make_openai_provider():
    # Import only if selected, so we don't require the 'openai' package by default
    from samos.api.image.openai_provider import OpenAIProvider
    return OpenAIProvider()

_provider_factories = {
    "stub": lambda: StubProvider(),
    "openai": _make_openai_provider,
}
_provider_cache = {}

def get_provider():
    name = os.getenv("IMAGE_PROVIDER", "stub").lower()
    factory = _provider_factories.get(name)
    if not factory:
        raise HTTPException(status_code=500, detail=f"Unknown IMAGE_PROVIDER: {name}")
    if name not in _provider_cache:
        _provider_cache[name] = factory()
    return _provider_cache[name]

def get_reference_image(default_fallback: str = "ref_alpha.jpg") -> str:
    # Read from env each call so you can change .env between runs
    return os.getenv("REFERENCE_IMAGE_ALPHA", default_fallback)

# -------------- Metrics helpers (NEW) ------------------
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

def _bucket_start(dt: datetime, period: str) -> datetime:
    # store naive UTC in DB (matches typical existing rows)
    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    if period == "hour":
        return dt.replace(minute=0, second=0, microsecond=0)
    if period == "day":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    raise ValueError("period must be 'hour' or 'day'")

def _bump_bucket(metric: str, period: str, ts: datetime, inc: int = 1) -> None:
    """Increment metrics_buckets row for (metric, period, bucket_start)."""
    bs = _bucket_start(ts, period)
    db = SessionLocal()
    try:
        # UPDATE first; if no row, INSERT
        row = db.execute(
            text(
                "SELECT id FROM metrics_buckets "
                "WHERE metric=:m AND period=:p AND bucket_start=:bs"
            ),
            {"m": metric, "p": period, "bs": bs},
        ).fetchone()

        if row:
            db.execute(
                text("UPDATE metrics_buckets SET value = value + :inc WHERE id=:id"),
                {"inc": inc, "id": row[0]},
            )
        else:
            db.execute(
                text(
                    "INSERT INTO metrics_buckets (metric, period, bucket_start, value) "
                    "VALUES (:m,:p,:bs,:v)"
                ),
                {"m": metric, "p": period, "bs": bs, "v": inc},
            )
        db.commit()
    except Exception:
        # We keep middleware resilient—skip persistence errors silently.
        db.rollback()
    finally:
        db.close()

def _bump_buckets(metric: str, ts: datetime, inc: int = 1) -> None:
    _bump_bucket(metric, "hour", ts, inc)
    _bump_bucket(metric, "day", ts, inc)

# -------------- Health & Metrics ------------------
@app.get("/health")
def health():
    provider = os.getenv("IMAGE_PROVIDER", "stub")
    return {"status": "ok", "provider": provider}

@app.get("/metrics")
def metrics():
    return dict(_METRICS)

@app.post("/metrics/reset")
def metrics_reset(also_buckets: bool = False, also_counters_table: bool = True):
    """
    Reset in-memory counters. Optionally wipe persisted rows.
    - also_buckets=True will DELETE FROM metrics_buckets (hour/day series)
    - also_counters_table=True will DELETE FROM metrics_counters (if in use)
    """
    # snapshot old values for response/debug
    before = dict(_METRICS)

    # clear in-memory counters
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
        except Exception:
            db.rollback()
        finally:
            db.close()

    # optional event
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
    except Exception:
        # metrics reset must never take down the server
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

# --- Request counter + buckets middleware (NEW/UPDATED) ---
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    ts = _utc_now()

    # in-memory counters
    _METRICS["http.requests"] += 1
    _METRICS[f"http.path:{request.url.path}"] += 1

    # persisted buckets
    _bump_buckets("http.requests", ts)
    _bump_buckets(f"http.path:{request.url.path}", ts)

    response = await call_next(request)
    return response

# -------------- Events (list/export) --------------
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
        sdt = _parse_iso(since)
        if sdt:
            q = q.filter(DBEvent.ts >= sdt)
        edt = _parse_iso(until)
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

# -------------- Sessions ------------------
@app.post("/session/start", response_model=SessionStartResponse)
def start_session():
    db = SessionLocal()
    try:
        sid = str(uuid4())
        sess = DBSession(id=sid, mode=DEFAULT_MODE)
        db.add(sess)
        db.commit()
        record_event("session.start", "Session created", sid, {"mode": sess.mode})
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
        return ModeGetResponse(session_id=req.session_id, mode=sess.mode)
    finally:
        db.close()

# -------------- Memory --------------------
@app.post("/memory")
def put_memory(req: MemoryPutRequest):
    db = SessionLocal()
    try:
        sess = db.query(DBSession).filter(DBSession.id == req.session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        item = db.query(DBMemory).filter(
            DBMemory.session_id == req.session_id, DBMemory.key == req.key
        ).first()
        if not item:
            item = DBMemory(
                session_id=req.session_id,
                key=req.key,
                value=req.value,
                meta_json=json.dumps(req.meta or {})
            )
        else:
            item.value = req.value
            item.meta_json = json.dumps(req.meta or {})
        db.add(item)
        db.commit()
        record_event("memory.put", "Memory saved", req.session_id, {"key": req.key})
        return {"ok": True}
    finally:
        db.close()

@app.get("/memory", response_model=MemoryItem)
def get_memory(session_id: str = Query(...), key: str = Query(...)):
    db = SessionLocal()
    try:
        item = db.query(DBMemory).filter(DBMemory.session_id == session_id, DBMemory.key == key).first()
        if not item:
            raise HTTPException(status_code=404, detail="Memory not found")
        return MemoryItem(
            key=item.key, value=item.value, meta=json.loads(item.meta_json or "{}"),
            created_at=item.created_at.isoformat() + "Z", updated_at=item.updated_at.isoformat() + "Z"
        )
    finally:
        db.close()

@app.get("/memory/list", response_model=MemoryListResponse)
def list_memory(session_id: str = Query(...)):
    db = SessionLocal()
    try:
        items = db.query(DBMemory).filter(DBMemory.session_id == session_id).all()
        return MemoryListResponse(items=[
            MemoryItem(
                key=i.key, value=i.value, meta=json.loads(i.meta_json or "{}"),
                created_at=i.created_at.isoformat() + "Z", updated_at=i.updated_at.isoformat() + "Z"
            ) for i in items
        ])
    finally:
        db.close()

# -------------- EMM -----------------------
@app.post("/emm")
def create_emm(req: EMMCreateRequest):
    db = SessionLocal()
    try:
        sess = db.query(DBSession).filter(DBSession.id == req.session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        e = DBEMM(
            session_id=req.session_id, type=req.type,
            message=req.message, meta_json=json.dumps(req.meta or {})
        )
        db.add(e)
        db.commit()
        record_event("emm.create", "EMM created", req.session_id, {"type": req.type})
        return {"ok": True, "id": e.id}
    finally:
        db.close()

@app.get("/emm/list", response_model=EMMListResponse)
def list_emms(session_id: str = Query(...), limit: int = Query(50)):
    db = SessionLocal()
    try:
        rows = db.query(DBEMM).filter(DBEMM.session_id == session_id)\
                               .order_by(DBEMM.id.desc())\
                               .limit(limit).all()
        return EMMListResponse(items=[
            EMMItem(
                id=r.id, type=r.type, message=r.message,
                meta=json.loads(r.meta_json or "{}"),
                created_at=r.created_at.isoformat() + "Z"
            )
            for r in rows
        ])
    finally:
        db.close()

@app.get("/emm/export", response_model=EMMListResponse)
def export_emms(session_id: str = Query(...)):
    db = SessionLocal()
    try:
        rows = db.query(DBEMM).filter(DBEMM.session_id == session_id)\
                               .order_by(DBEMM.id.asc()).all()
        return EMMListResponse(items=[
            EMMItem(
                id=r.id, type=r.type, message=r.message,
                meta=json.loads(r.meta_json or "{}"),
                created_at=r.created_at.isoformat() + "Z"
            )
            for r in rows
        ])
    finally:
        db.close()

# -------------- Images --------------------
@app.post("/image/generate", response_model=ImageGenerateResponse)
def generate_image(req: ImageGenerateRequest):
    db = SessionLocal()
    try:
        # Verify session exists
        sess = db.query(DBSession).filter(DBSession.id == req.session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")

        provider = get_provider()

        # Reference image: request value if present; otherwise env fallback
        reference = getattr(req, "reference_image", None) or get_reference_image()

        try:
            # Generate via provider
            result = provider.generate(
                session_id=req.session_id,
                prompt=req.prompt,
                reference_image=reference
            )

            # Persist success
            img = DBImage(
                id=result["image_id"],
                session_id=req.session_id,
                prompt=req.prompt,
                provider=result["provider"],
                url=result["url"],
                reference_used=result["reference_used"],
                status=result.get("status", "ok"),
                meta_json=json.dumps(result.get("meta", {}))
            )
            db.add(img)
            db.commit()

            # Event + metrics (in-memory and buckets)
            record_event(
                "image.generate.ok", "Image created", req.session_id,
                {"provider": result.get("provider"), "image_id": result.get("image_id")}
            )
            _METRICS["image.ok"] += 1
            ts = _utc_now()
            _bump_buckets("image.ok", ts)

            return ImageGenerateResponse(**result)

        except Exception as e:
            # OneBounce on failure
            emm = DBEMM(
                session_id=req.session_id,
                type="OneBounce",
                message=str(e),
                meta_json=json.dumps({"prompt": req.prompt})
            )
            db.add(emm)
            db.commit()

            # Persist failed image record
            img = DBImage(
                id=str(uuid4()),
                session_id=req.session_id,
                prompt=req.prompt,
                provider=getattr(provider, "name", "unknown"),
                url="",
                reference_used=reference,
                status="failed",
                meta_json=json.dumps({"error": str(e)})
            )
            db.add(img)
            db.commit()

            # Event + metrics
            record_event("image.generate.fail", "Image failed", req.session_id, {"error": str(e)})
            _METRICS["image.fail"] += 1
            ts = _utc_now()
            _bump_buckets("image.fail", ts)

            raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")

    finally:
        db.close()

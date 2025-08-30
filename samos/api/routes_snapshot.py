# samos/api/routes_snapshot.py

from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session as OrmSession

from samos.api.db import SessionLocal, get_db
from samos.api.obs.events import record_event
from samos.api.settings import ADMIN_TOKEN, SNAPSHOT_DIR
from samos.api.snapshot_service import make_snapshot, store_snapshot

router = APIRouter()

# Must match what /snapshot writes
SCHEMA_VERSION = 3


# ---------- Pydantic models (strict validation) ----------


class SnapshotModel(BaseModel):
    schema_version: int
    created_at: datetime
    app_version: Optional[str] = None
    sessions: list
    memories: list = []
    emms: list = []
    images: list = []
    events: list = []
    metrics: dict = {"counters": [], "buckets": []}


class RestoreEnvelope(BaseModel):
    snapshot: SnapshotModel


# ---------- GET /snapshot ----------


@router.get("/snapshot")
def get_snapshot(
    include: str = "active",  # 'active' or 'all'
    events_per_session: int = 100,
    active_hours: int = 24,
    include_metrics: bool = True,
    store: bool = True,
    db: OrmSession = Depends(get_db),
):
    snap = make_snapshot(
        db,
        include=include,
        events_per_session=events_per_session,
        active_hours=active_hours,
        include_metrics=include_metrics,
    )

    record_event(
        "snapshot.create",
        "Snapshot created",
        None,
        {
            "include": include,
            "events_per_session": events_per_session,
            "active_hours": active_hours,
            "include_metrics": include_metrics,
            "store": store,
        },
    )

    if store:
        path = store_snapshot(snap)
        return {"snapshot": snap, "stored_as": str(path)}
    return {"snapshot": snap}


# ---------- POST /restore (strict, atomic, logged) ----------


@router.post("/restore")
def post_restore(
    payload: RestoreEnvelope = Body(...),  # {} -> 422 automatically
    mode: str = Query("replace"),  # 'replace' or 'merge' (we implement 'replace')
    # Accept BOTH common spellings; Swagger sometimes sends x-admin-token
    x_admin_token: Optional[str] = Header(None, alias="x_admin_token"),
    x_admin_token_alt: Optional[str] = Header(None, alias="x-admin-token"),
):
    # --- auth ---
    token = x_admin_token or x_admin_token_alt
    if not token:
        raise HTTPException(status_code=422, detail="Missing x_admin_token header")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

    snap = payload.snapshot

    # --- schema version enforcement ---
    if snap.schema_version != SCHEMA_VERSION:
        record_event(
            "recovery.fail",
            "Restore rejected: schema version mismatch",
            None,
            {"expected": SCHEMA_VERSION, "got": snap.schema_version},
        )
        raise HTTPException(status_code=400, detail="Snapshot schema version mismatch")

    # --- apply restore (simple, dependency-safe order) ---
    db = SessionLocal()
    try:
        if mode == "replace":
            # FK-safe wipe order
            for tbl in (
                "events",
                "images",
                "emms",
                "memories",
                "sessions",
                "metrics_buckets",
                "metrics_counters",
            ):
                try:
                    db.execute(f"DELETE FROM {tbl}")
                except Exception:
                    # table may not exist; ignore
                    pass

        # sessions
        for s in snap.sessions:
            db.execute(
                "INSERT OR REPLACE INTO sessions (id, mode, created_at, updated_at) "
                "VALUES (:id,:mode,:ca,:ua)",
                {
                    "id": s["id"],
                    "mode": s.get("mode"),
                    "ca": s.get("created_at"),
                    "ua": s.get("updated_at"),
                },
            )

        # memories
        for m in snap.memories:
            db.execute(
                "INSERT INTO memories (session_id, key, value, meta_json, created_at, updated_at) "
                "VALUES (:sid,:key,:value,:meta,:ca,:ua)",
                {
                    "sid": m["session_id"],
                    "key": m["key"],
                    "value": m.get("value", ""),
                    "meta": m.get("meta_json", "{}"),
                    "ca": m.get("created_at"),
                    "ua": m.get("updated_at"),
                },
            )

        # images (wrapped SQL to satisfy line-length rules)
        for i in snap.images:
            db.execute(
                text(
                    "INSERT INTO images "
                    "(id, session_id, prompt, provider, url, reference_used, status, meta_json, created_at) "
                    "VALUES (:id, :sid, :prompt, :provider, :url, :ref, :status, :meta, :ca)"
                ),
                {
                    "id": i["id"],
                    "sid": i["session_id"],
                    "prompt": i.get("prompt", ""),
                    "provider": i.get("provider", ""),
                    "url": i.get("url", ""),
                    "ref": i.get("reference_used", ""),
                    "status": i.get("status", "ok"),
                    "meta": i.get("meta_json", "{}"),
                    "ca": i.get("created_at"),
                },
            )

        # events
        for e in snap.events:
            db.execute(
                "INSERT INTO events (id, session_id, ts, kind, message, meta_json) "
                "VALUES (:id,:sid,:ts,:kind,:msg,:meta)",
                {
                    "id": e.get("id"),
                    "sid": e.get("session_id"),
                    "ts": e.get("ts"),
                    "kind": e.get("kind"),
                    "msg": e.get("message", ""),
                    "meta": e.get("meta_json", "{}"),
                },
            )

        # metrics (optional)
        for c in snap.metrics.get("counters", []):
            db.execute(
                "INSERT OR REPLACE INTO metrics_counters (key, value, updated_at) "
                "VALUES (:key,:value,:ua)",
                {
                    "key": c["key"],
                    "value": c.get("value", 0),
                    "ua": c.get("updated_at"),
                },
            )
        for b in snap.metrics.get("buckets", []):
            db.execute(
                "INSERT INTO metrics_buckets (metric, period, bucket_start, value) "
                "VALUES (:m,:p,:bs,:v)",
                {
                    "m": b["metric"],
                    "p": b["period"],
                    "bs": b["bucket_start"],
                    "v": b.get("value", 0),
                },
            )

        db.commit()
        record_event("snapshot.restore", "Snapshot restored", None, {"mode": mode})
        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        record_event("recovery.fail", "Restore failed", None, {"error": str(e)})
        raise HTTPException(
            status_code=400, detail="Restore failed: invalid or inconsistent snapshot"
        )
    finally:
        db.close()


# ---------- GET /backups ----------


@router.get("/backups")
def list_backups():
    p = Path(SNAPSHOT_DIR)
    files = []
    if p.exists():
        for f in sorted(p.glob("snapshot-*.json")):
            files.append({"name": f.name, "size_bytes": f.stat().st_size})
    return {"files": files}

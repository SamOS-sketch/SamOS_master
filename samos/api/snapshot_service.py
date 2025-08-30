# samos/api/snapshot_service.py
"""
Snapshot + store helpers (Phase 7.5 hardened)

- make_snapshot(...) builds a JSON-serializable snapshot of:
  sessions, memories, images, events, and metrics.
- store_snapshot(snapshot_dict) writes the snapshot to SNAPSHOT_DIR
  using a Windows-safe filename.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session as OrmSession

from samos.api.settings import SNAPSHOT_DIR

SCHEMA_VERSION = 3
APP_VERSION = "samOS api 0.7.0"


# ---------- helpers ----------


def _dt(obj) -> Optional[str]:
    if not obj:
        return None
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            return obj.replace(tzinfo=timezone.utc).isoformat()
        return obj.isoformat()
    return str(obj)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(ts: datetime) -> str:
    return ts.replace(tzinfo=timezone.utc).isoformat().replace(":", "-")


def _try_read_live_metrics() -> Dict[str, int]:
    try:
        from samos.api.main import _METRICS  # type: ignore

        if isinstance(_METRICS, Counter):
            return dict(_METRICS)
        if isinstance(_METRICS, dict):
            return dict(_METRICS)
    except Exception:
        pass
    return {}


def _read_persisted_metrics(db: OrmSession) -> Dict[str, Any]:
    out = {"counters": [], "buckets": []}

    # counters
    try:
        rows = db.execute(
            text("SELECT key, value, updated_at FROM metrics_counters")
        ).fetchall()
        for r in rows:
            out["counters"].append(
                {"key": r[0], "value": int(r[1] or 0), "updated_at": _dt(r[2])}
            )
    except Exception:
        pass

    # buckets
    try:
        rows = db.execute(
            text("SELECT metric, period, bucket_start, value FROM metrics_buckets")
        ).fetchall()
        for r in rows:
            out["buckets"].append(
                {
                    "metric": r[0],
                    "period": r[1],
                    "bucket_start": _dt(r[2]),
                    "value": int(r[3] or 0),
                }
            )
    except Exception:
        pass

    return out


def _merge_live_into_persisted(
    live: Dict[str, int], persisted: Dict[str, Any]
) -> Dict[str, Any]:
    counters_by_key = {c["key"]: c for c in persisted.get("counters", [])}
    for k, v in live.items():
        counters_by_key[k] = {"key": k, "value": int(v), "updated_at": _now_iso()}
    return {
        "counters": list(counters_by_key.values()),
        "buckets": list(persisted.get("buckets", [])),
    }


# ---------- main API ----------


def make_snapshot(
    db: OrmSession,
    *,
    include: str = "active",  # 'active' | 'all'
    events_per_session: int = 100,
    active_hours: int = 24,
    include_metrics: bool = True,
) -> Dict[str, Any]:
    created = datetime.now(timezone.utc)

    # Sessions
    sessions: List[Dict[str, Any]] = []
    if include == "all":
        rows = db.execute(
            text("SELECT id, mode, created_at, updated_at FROM sessions")
        ).fetchall()
    else:
        cutoff = created - timedelta(hours=active_hours)
        rows = db.execute(
            text(
                "SELECT id, mode, created_at, updated_at "
                "FROM sessions "
                "WHERE (updated_at IS NOT NULL AND updated_at >= :cut) "
                "   OR (created_at IS NOT NULL AND created_at >= :cut)"
            ),
            {"cut": cutoff},
        ).fetchall()

    sess_ids: List[str] = []
    for r in rows:
        sess_ids.append(r[0])
        sessions.append(
            {
                "id": r[0],
                "mode": r[1],
                "created_at": _dt(r[2]),
                "updated_at": _dt(r[3]),
            }
        )

    # Memories
    memories: List[Dict[str, Any]] = []
    if sess_ids:
        stmt = text(
            "SELECT id, session_id, key, value, meta_json, created_at, updated_at "
            "FROM memories WHERE session_id IN :ids"
        ).bindparams(bindparam("ids", expanding=True))
        mrows = db.execute(stmt, {"ids": list(sess_ids)}).fetchall()
    else:
        mrows = []

    for r in mrows:
        memories.append(
            {
                "id": r[0],
                "session_id": r[1],
                "key": r[2],
                "value": r[3],
                "meta_json": r[4] or "{}",
                "created_at": _dt(r[5]),
                "updated_at": _dt(r[6]),
            }
        )

    # Images
    images: List[Dict[str, Any]] = []
    if sess_ids:
        stmt = text(
            "SELECT id, session_id, prompt, provider, url, reference_used, status, meta_json, created_at "
            "FROM images WHERE session_id IN :ids"
        ).bindparams(bindparam("ids", expanding=True))
        irows = db.execute(stmt, {"ids": list(sess_ids)}).fetchall()
    else:
        irows = []

    for r in irows:
        images.append(
            {
                "id": r[0],
                "session_id": r[1],
                "prompt": r[2],
                "provider": r[3],
                "url": r[4],
                "reference_used": r[5],
                "status": r[6],
                "meta_json": r[7] or "{}",
                "created_at": _dt(r[8]),
            }
        )

    # Events (limit per session)
    events: List[Dict[str, Any]] = []
    for sid in sess_ids:
        erows = db.execute(
            text(
                "SELECT id, session_id, ts, kind, message, meta_json "
                "FROM events WHERE session_id = :sid "
                "ORDER BY id DESC LIMIT :lim"
            ),
            {"sid": sid, "lim": events_per_session},
        ).fetchall()
        for r in erows:
            events.append(
                {
                    "id": r[0],
                    "session_id": r[1],
                    "ts": _dt(r[2]),
                    "kind": r[3],
                    "message": r[4],
                    "meta_json": r[5] or "{}",
                }
            )

    # Global (no-session) events
    nrows = db.execute(
        text(
            "SELECT id, session_id, ts, kind, message, meta_json "
            "FROM events WHERE session_id IS NULL "
            "ORDER BY id DESC LIMIT :lim"
        ),
        {"lim": events_per_session},
    ).fetchall()
    for r in nrows:
        events.append(
            {
                "id": r[0],
                "session_id": r[1],
                "ts": _dt(r[2]),
                "kind": r[3],
                "message": r[4],
                "meta_json": r[5] or "{}",
            }
        )

    # Metrics
    metrics = {"counters": [], "buckets": []}
    if include_metrics:
        persisted = _read_persisted_metrics(db)
        live = _try_read_live_metrics()
        metrics = _merge_live_into_persisted(live, persisted)

    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _dt(created),
        "app_version": APP_VERSION,
        "sessions": sessions,
        "memories": memories,
        "emms": [],  # reserved
        "images": images,
        "events": events,
        "metrics": metrics,
    }
    return snapshot


def store_snapshot(result: Dict[str, Any]) -> Path:
    import json

    snapshot = (
        result.get("snapshot")
        if isinstance(result, dict) and "snapshot" in result
        else result
    )
    ts = datetime.now(timezone.utc)
    fname = f"snapshot-{_safe_filename(ts)}.json"
    outdir = Path(SNAPSHOT_DIR)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / fname

    with path.open("w", encoding="utf-8") as f:
        json.dump({"snapshot": snapshot}, f, ensure_ascii=False, indent=2)

    return path

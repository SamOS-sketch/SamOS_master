# samos/api/routes_ops.py
from __future__ import annotations

import os
import json
import sqlite3
import subprocess
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

router = APIRouter(prefix="/ops", tags=["ops"])


# ----------------------------
# DB helpers (SQLite-safe)
# ----------------------------

def _db_url() -> str:
    # Canonical env var (you may also have DATABASE_URL or SAMOS_DB_URL elsewhere)
    return (
        os.getenv("SAM_DB_URL")
        or os.getenv("SAMOS_DB_URL")
        or os.getenv("DATABASE_URL")
        or "sqlite:///./memory/samos.db"
    )


def _sqlite_path_from_url(db_url: str) -> Optional[str]:
    if not db_url.startswith("sqlite"):
        return None
    # Accept sqlite:///./memory/samos.db or sqlite:////abs/path
    if db_url.startswith("sqlite:///"):
        return db_url[len("sqlite:///"):]
    if db_url.startswith("sqlite:////"):
        # Windows can still use this; keep as /abs/path
        return db_url[len("sqlite:////"):]
    if db_url.startswith("sqlite://"):
        return db_url[len("sqlite://"):]
    return None


def _sqlite_path() -> str:
    # Always return a usable path on disk (relative is fine)
    p = os.getenv("SAM_SQLITE_PATH")
    if p:
        return p

    db_url = _db_url()
    sp = _sqlite_path_from_url(db_url)
    if sp:
        return sp

    # fallback
    return "./memory/samos.db"


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(_sqlite_path())
    con.row_factory = sqlite3.Row
    return con


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    cur = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    )
    return cur.fetchone() is not None


def _cols(con: sqlite3.Connection, table: str) -> List[str]:
    if not _table_exists(con, table):
        return []
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return [r["name"] for r in rows]


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _ok(label: str, payload: Any = None) -> Dict[str, Any]:
    # Keep responses PowerShell-friendly
    return {"ok": True, "label": label, "data": payload}


def _fail(label: str, error: str, payload: Any = None) -> Dict[str, Any]:
    return {"ok": False, "label": label, "error": error, "data": payload}


# ----------------------------
# Ops endpoints
# ----------------------------

@router.get("/ping")
def ping():
    return _ok("ping", True)


@router.get("/db")
def db_info():
    db_url = _db_url()
    sqlite_path = _sqlite_path()
    exists = os.path.exists(sqlite_path)
    size_bytes = os.path.getsize(sqlite_path) if exists else 0
    return _ok(
        "db",
        {
            "db_url": db_url,
            "sqlite_path": sqlite_path,
            "sqlite_exists": exists,
            "sqlite_size_bytes": size_bytes,
        },
    )


@router.get("/alembic")
def alembic_head():
    """
    Reads alembic current head.
    Works even if multiple heads exist (will return the raw output).
    """
    try:
        # "alembic current" prints something like: "<rev> (head)" or "(mergepoint)"
        out = subprocess.check_output(["alembic", "current"], text=True, stderr=subprocess.STDOUT)
        out = (out or "").strip()
        # Best-effort: pull first token that looks like a revision
        head = None
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            tok = line.split()[0]
            if tok and all(c in "0123456789abcdef" for c in tok.lower()):
                head = tok
                break
        return _ok("alembic_head", head or out)
    except Exception as e:
        return _fail("alembic_head", str(e))


@router.get("/schema/{table_name}")
def schema(table_name: str):
    try:
        with _connect() as con:
            if not _table_exists(con, table_name):
                return _fail("schema", f"table '{table_name}' not found", {"table": table_name, "columns": []})
            rows = con.execute(f"PRAGMA table_info({table_name})").fetchall()
            cols = []
            for r in rows:
                cols.append(
                    {
                        "cid": r["cid"],
                        "name": r["name"],
                        "type": r["type"],
                        "notnull": bool(r["notnull"]),
                        "default": r["dflt_value"],
                        "pk": bool(r["pk"]),
                    }
                )
            return _ok("schema", {"table": table_name, "columns": cols})
    except Exception as e:
        return _fail("schema", str(e), {"table": table_name, "columns": []})


# ---- sessions ----

@router.get("/sessions")
def ops_sessions():
    """
    Returns count + (optional) small sample list if table exists.
    """
    try:
        with _connect() as con:
            if not _table_exists(con, "sessions"):
                # Some builds don’t persist sessions as rows (your /session/start just emits events)
                return _ok("count_sessions", 0)

            cnt = con.execute("SELECT COUNT(1) AS c FROM sessions").fetchone()["c"]
            # Small sample of most recent (if there is a created_at column)
            cols = _cols(con, "sessions")
            order = "ORDER BY created_at DESC" if "created_at" in cols else ""
            rows = con.execute(f"SELECT * FROM sessions {order} LIMIT 5").fetchall()
            sample = [dict(r) for r in rows]
            return _ok("count_sessions", {"count": _safe_int(cnt), "sample": sample})
    except Exception as e:
        return _fail("count_sessions", str(e))


@router.get("/sessions/{session_id}")
def ops_session_by_id(session_id: str):
    try:
        with _connect() as con:
            if not _table_exists(con, "sessions"):
                return _ok("session", {})
            rows = con.execute("SELECT * FROM sessions WHERE id = ? LIMIT 1", (session_id,)).fetchall()
            return _ok("session", dict(rows[0]) if rows else {})
    except Exception as e:
        return _fail("session", str(e))


# ---- memory ----

@router.get("/memory")
def ops_memory():
    """
    Uses 'memories' table (your schema shows: id, session_id, content, created_at, ...)
    """
    try:
        with _connect() as con:
            if not _table_exists(con, "memories"):
                return _ok("count_memories", 0)
            cnt = con.execute("SELECT COUNT(1) AS c FROM memories").fetchone()["c"]
            return _ok("count_memories", {"count": _safe_int(cnt)})
    except Exception as e:
        return _fail("count_memories", str(e))


# ---- events ----

@router.get("/events")
def ops_events():
    try:
        with _connect() as con:
            if not _table_exists(con, "events"):
                return _ok("count_events", 0)
            cnt = con.execute("SELECT COUNT(1) AS c FROM events").fetchone()["c"]
            cols = _cols(con, "events")
            order = "ORDER BY created_at DESC" if "created_at" in cols else "ORDER BY id DESC"
            rows = con.execute(f"SELECT * FROM events {order} LIMIT 5").fetchall()
            sample = [dict(r) for r in rows]
            return _ok("count_events", {"count": _safe_int(cnt), "sample": sample})
    except Exception as e:
        return _fail("count_events", str(e))


@router.get("/events/{event_id}")
def ops_event_by_id(event_id: int):
    try:
        with _connect() as con:
            if not _table_exists(con, "events"):
                return _ok("event", {})
            rows = con.execute("SELECT * FROM events WHERE id = ? LIMIT 1", (event_id,)).fetchall()
            return _ok("event", dict(rows[0]) if rows else {})
    except Exception as e:
        return _fail("event", str(e))


# ---- images ----

def _image_select_cols(con: sqlite3.Connection) -> List[str]:
    """
    Select columns that exist across different migration states.
    """
    existing = set(_cols(con, "images"))
    preferred = [
        "id",
        "session_id",
        "created_at",
        "prompt",
        "provider",
        "tier",
        "status",
        "latency_ms",
        "drift_score",
        "url",
        "local_path",
        "provenance",
        "ref_used",
        "mode",
        "alpha_id",
        "seed",
        "meta_json",
    ]
    return [c for c in preferred if c in existing]


@router.get("/images")
def ops_images():
    try:
        with _connect() as con:
            if not _table_exists(con, "images"):
                return _ok("count_images", 0)

            cnt = con.execute("SELECT COUNT(1) AS c FROM images").fetchone()["c"]
            cols = _image_select_cols(con)
            if not cols:
                return _ok("count_images", {"count": _safe_int(cnt), "items": []})

            # Newest first if possible
            existing = set(_cols(con, "images"))
            order = "ORDER BY created_at DESC" if "created_at" in existing else "ORDER BY rowid DESC"
            sql = f"SELECT {', '.join(cols)} FROM images {order} LIMIT 10"
            rows = con.execute(sql).fetchall()

            items = []
            for r in rows:
                d = dict(r)
                # If meta_json exists, try to parse it for readability
                if "meta_json" in d and isinstance(d["meta_json"], str):
                    try:
                        d["meta_json"] = json.loads(d["meta_json"])
                    except Exception:
                        pass
                items.append(d)

            return _ok("count_images", {"count": _safe_int(cnt), "items": items})
    except Exception as e:
        return _fail("count_images", str(e))


@router.get("/images/{image_id}")
def ops_image_by_id(image_id: str):
    try:
        with _connect() as con:
            if not _table_exists(con, "images"):
                return _ok("image", {})
            cols = _image_select_cols(con)
            if not cols:
                return _ok("image", {})
            sql = f"SELECT {', '.join(cols)} FROM images WHERE id = ? LIMIT 1"
            rows = con.execute(sql, (image_id,)).fetchall()
            if not rows:
                return _ok("image", {})
            d = dict(rows[0])
            if "meta_json" in d and isinstance(d["meta_json"], str):
                try:
                    d["meta_json"] = json.loads(d["meta_json"])
                except Exception:
                    pass
            return _ok("image", d)
    except Exception as e:
        return _fail("image", str(e))

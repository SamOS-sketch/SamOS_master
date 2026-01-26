# samos/api/routes_sessions.py
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

try:
    from samos.core.settings import settings  # type: ignore
except Exception:
    settings = None  # pragma: no cover


router = APIRouter(tags=["sessions"])

_SAFE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# ----------------------------
# DB resolution (must match ops)
# ----------------------------
def _resolve_db_url() -> str:
    """
    Resolve DB url from:
    1) ENV DATABASE_URL
    2) settings.SAMOS_DB_URL (if available)
    3) default sqlite:///./memory/samos.db
    """
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    if settings is not None:
        url = getattr(settings, "SAMOS_DB_URL", None)
        if url:
            return url

    return "sqlite:///./memory/samos.db"


def _sqlite_path_from_url(db_url: str) -> Path:
    if not db_url.startswith("sqlite:///"):
        raise RuntimeError(f"Only sqlite:/// URLs are supported (got: {db_url})")
    rel = db_url.replace("sqlite:///", "", 1)
    return Path(rel).resolve()


def _sqlite_connect() -> sqlite3.Connection:
    db_url = _resolve_db_url()
    p = _sqlite_path_from_url(db_url)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    return con


def _table_columns(table: str) -> List[str]:
    if not _SAFE_NAME_RE.match(table):
        raise HTTPException(status_code=400, detail="Invalid table name")
    con = _sqlite_connect()
    try:
        cur = con.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        cols = cur.fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()
    return [c["name"] for c in cols]


def _table_exists(table: str) -> bool:
    return len(_table_columns(table)) > 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------------------
# Write helpers (schema-tolerant)
# ----------------------------
def _insert_session_row(con: sqlite3.Connection, sid: str, mode: str, persona: str) -> None:
    if not _table_exists("sessions"):
        return

    cols = _table_columns("sessions")
    # choose best timestamp column
    ts_col = "created_at" if "created_at" in cols else ("ts" if "ts" in cols else None)

    data: Dict[str, Any] = {}
    if "id" in cols:
        data["id"] = sid
    elif "session_id" in cols:
        data["session_id"] = sid
    else:
        # no obvious identifier column
        return

    if "mode" in cols:
        data["mode"] = mode
    if "persona" in cols:
        data["persona"] = persona
    if ts_col is not None:
        data[ts_col] = _now_iso()

    keys = list(data.keys())
    if not keys:
        return

    ph = ",".join(["?"] * len(keys))
    sql = f"INSERT OR IGNORE INTO sessions ({','.join(keys)}) VALUES ({ph})"
    con.execute(sql, tuple(data[k] for k in keys))


def _insert_event_row(con: sqlite3.Connection, sid: str, kind: str, message: str, payload: Dict[str, Any]) -> None:
    if not _table_exists("events"):
        return

    cols = _table_columns("events")
    ts_col = "ts" if "ts" in cols else ("created_at" if "created_at" in cols else None)

    data: Dict[str, Any] = {}

    # session link
    if "session_id" in cols:
        data["session_id"] = sid

    # kind / type naming
    if "kind" in cols:
        data["kind"] = kind
    elif "type" in cols:
        data["type"] = kind
    elif "name" in cols:
        data["name"] = kind

    # message
    if "message" in cols:
        data["message"] = message

    # payload/meta storage
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    if "meta_json" in cols:
        data["meta_json"] = payload_json
    elif "payload" in cols:
        data["payload"] = payload_json

    if ts_col is not None:
        data[ts_col] = _now_iso()

    keys = [k for k in data.keys() if k in cols]
    if not keys:
        return

    ph = ",".join(["?"] * len(keys))
    sql = f"INSERT INTO events ({','.join(keys)}) VALUES ({ph})"
    con.execute(sql, tuple(data[k] for k in keys))


# ----------------------------
# API
# ----------------------------
@router.post("/session/start")
def session_start(body: Optional[Dict[str, Any]] = None):
    """
    V1 session start:
    - Generates session_id
    - Writes sessions row (if table exists)
    - Writes session.start event row (if table exists)
    - Returns session_id
    """
    body = body or {}
    sid = str(uuid.uuid4())
    mode = str(body.get("mode") or "work")
    persona = str(body.get("persona") or "private")

    con = _sqlite_connect()
    try:
        con.execute("BEGIN")
        _insert_session_row(con, sid, mode, persona)
        _insert_event_row(con, sid, "session.start", "begin", {"mode": mode, "persona": persona})
        con.commit()
    except Exception:
        con.rollback()
        # Even if DB write fails, still return a session id (but you want to know!)
        return {"ok": False, "session_id": sid, "warning": "DB write failed; check schema/logs"}
    finally:
        con.close()

    return {"ok": True, "session_id": sid, "mode": mode, "persona": persona}

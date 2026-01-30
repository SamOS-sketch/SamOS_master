# samos/api/routes_ops.py
from __future__ import annotations

import binascii
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/ops", tags=["ops"])

# .../samos/api/routes_ops.py -> parents[2] == project root (SamOS_master)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------- helpers ----------------

def _ok(label: str, data: Any) -> Dict[str, Any]:
    return {"ok": True, "label": label, "data": data}


def _fail(label: str, msg: str, status_code: int = 404, **extra: Any):
    raise HTTPException(
        status_code=status_code,
        detail={"ok": False, "label": label, "error": {"msg": msg, **extra}},
    )


def _strip_wrapping_quotes(s: str) -> str:
    s = (s or "").strip()
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        return s[1:-1].strip()
    return s


def _normalize(s: str) -> str:
    """
    Robust ID normalizer:
    - trim
    - strip wrapping quotes
    - NFKC normalize
    - remove unicode control chars (category startswith 'C' e.g. Cf, Cc)
    - casefold for stable comparison
    """
    s = _strip_wrapping_quotes(s)
    s = unicodedata.normalize("NFKC", s)
    s = "".join(c for c in s if not unicodedata.category(c).startswith("C"))
    return s.strip().casefold()


def _to_hex(s: str) -> str:
    try:
        return binascii.hexlify((s or "").encode("utf-8")).decode("ascii")
    except Exception:
        return ""


def _db_path() -> Path:
    # canonical DB location for the API
    return (PROJECT_ROOT / "memory" / "samos.db").resolve()


def _connect() -> tuple[sqlite3.Connection, Path]:
    p = _db_path()
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    return con, p


def _row_to_dict(r: sqlite3.Row) -> Dict[str, Any]:
    return dict(r)


def _id_diagnostics(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        raw = r["id"]
        raw_s = raw if isinstance(raw, str) else str(raw)
        out.append(
            {
                "id": raw_s,
                "repr": repr(raw_s),
                "len": len(raw_s),
                "hex_utf8": _to_hex(raw_s),
                "norm": _normalize(raw_s),
            }
        )
    return out


# ---------------- endpoints ----------------

@router.get("/db")
def ops_db():
    _, p = _connect()
    return _ok(
        "db",
        {
            "sqlite_path": str(p),
            "exists": p.exists(),
            "size": p.stat().st_size if p.exists() else 0,
        },
    )


@router.get("/images")
def ops_list_images():
    """
    Lists rows from the images table.
    Note: we preserve the stored id, and add id_norm for robustness.
    """
    con, p = _connect()
    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM images ORDER BY created_at DESC")
        rows = cur.fetchall()

        items: List[Dict[str, Any]] = []
        for r in rows:
            d = _row_to_dict(r)
            raw_id = d.get("id", "")
            raw_id = raw_id if isinstance(raw_id, str) else str(raw_id)
            d["id"] = raw_id
            d["id_norm"] = _normalize(raw_id)
            items.append(d)

        return _ok(
            "count_images",
            {
                "count": len(items),
                "items": items,
                "db": str(p),
            },
        )
    finally:
        con.close()


@router.get("/images_debug")
def ops_images_debug():
    """
    Debug helper: shows raw + repr + hex + normalized ids.
    """
    con, p = _connect()
    try:
        cur = con.cursor()
        cur.execute("SELECT id FROM images ORDER BY created_at DESC")
        rows = cur.fetchall()
        return _ok(
            "images_debug",
            {
                "db": str(p),
                "count": len(rows),
                "ids": _id_diagnostics(rows),
            },
        )
    finally:
        con.close()


@router.get("/images/{image_id}")
def ops_get_image(image_id: str):
    """
    Returns the IMAGE RECORD (row) when it exists in SQLite.

    Matching rule:
    - compare normalized requested id to normalized stored ids
    - this supports ids copied from /ops/images (raw) or any normalized variant
    """
    asked_raw = image_id
    asked_norm = _normalize(image_id)

    con, p = _connect()
    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM images ORDER BY created_at DESC")
        rows = cur.fetchall()

        for r in rows:
            stored = r["id"]
            stored_s = stored if isinstance(stored, str) else str(stored)
            if _normalize(stored_s) == asked_norm:
                d = _row_to_dict(r)
                d["id"] = stored_s
                d["id_norm"] = _normalize(stored_s)
                return _ok("image", {"db": str(p), "item": d})

        _fail(
            "image_not_found",
            "image not found",
            asked_for=asked_raw,
            asked_norm=asked_norm,
            asked_len=len(asked_raw or ""),
            asked_hex_utf8=_to_hex(asked_raw or ""),
            db=str(p),
            ids_visible=_id_diagnostics(rows),
        )
    finally:
        con.close()

# tests/test_ops_images.py
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Import AFTER standard libs to avoid any side-effects before test setup
from samos.api.main import app


def _project_root() -> Path:
    # .../SamOS_master/tests/test_ops_images.py -> parents[1] == SamOS_master
    return Path(__file__).resolve().parents[1]


def _db_path() -> Path:
    return (_project_root() / "memory" / "samos.db").resolve()


def _ensure_images_table(con: sqlite3.Connection) -> None:
    # Minimal schema sufficient for ops endpoints
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS images (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            url TEXT,
            local_path TEXT,
            status TEXT,
            meta_json TEXT,
            created_at TEXT
        )
        """
    )
    con.commit()


def _insert_image(con: sqlite3.Connection, image_id: str) -> None:
    con.execute(
        """
        INSERT OR REPLACE INTO images (id, session_id, url, local_path, status, meta_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            image_id,
            "pytest-session",
            "https://example.invalid/image.png",
            None,
            "ok",
            '{"source":"pytest"}',
            str(time.time()),
        ),
    )
    con.commit()


def _delete_image(con: sqlite3.Connection, image_id: str) -> None:
    con.execute("DELETE FROM images WHERE id = ?", (image_id,))
    con.commit()


@pytest.mark.order(1)
def test_ops_images_list_and_get_by_id_roundtrip():
    """
    Regression guard:
    - /ops/images returns 200 and includes inserted id
    - /ops/images/{id} returns 200 for that same id
    If duplicate route registration returns, this tends to fail fast.
    """
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    image_id = "pytest_" + str(int(time.time() * 1000))

    con = sqlite3.connect(str(db_path))
    try:
        _ensure_images_table(con)
        _insert_image(con, image_id)

        client = TestClient(app)

        # List
        r = client.get("/ops/images")
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload.get("ok") is True, payload
        items = payload.get("data", {}).get("items", [])
        ids = [it.get("id") for it in items]
        assert image_id in ids, {"expected_id": image_id, "ids_seen": ids[:25]}

        # Get by id
        r2 = client.get(f"/ops/images/{image_id}")
        assert r2.status_code == 200, r2.text
        payload2 = r2.json()
        assert payload2.get("ok") is True, payload2
        item = payload2.get("data", {}).get("item") or payload2.get("data", {})
        # Some implementations return {"item": {...}}; some return row directly.
        got_id = item.get("id") if isinstance(item, dict) else None
        assert got_id == image_id, {"expected": image_id, "got": got_id, "payload": payload2}

    finally:
        try:
            _delete_image(con, image_id)
        finally:
            con.close()

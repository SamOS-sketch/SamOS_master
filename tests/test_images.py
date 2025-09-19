# tests/test_images.py
from __future__ import annotations

import json
import os
import sqlite3
import importlib
from pathlib import Path
from typing import Any, Dict

from alembic.config import Config
from alembic import command
from fastapi.testclient import TestClient


# ---------- Alembic: migrate a brand-new DB file ----------
def _init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(alembic_cfg, "head")


# ---------- Build a TestClient for the real app ----------
def _make_client(db_path: Path) -> TestClient:
    # Minimal, test-friendly environment
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["IMAGE_PROVIDER"] = "stub"
    os.environ["DRIFT_METHOD"] = "phash"            # quick + light
    os.environ["DRIFT_THRESHOLD"] = "0.35"
    os.environ["REFERENCE_IMAGE_ALPHA"] = ""        # no external file dependency
    os.environ["SAM_MODE_DEFAULT"] = "work"
    os.environ["SAMOS_PERSONA"] = "private"

    # Import after env is set so settings pick them up
    main_mod = importlib.import_module("samos.api.main")
    # If the module was imported before, reload to pick up new env
    main_mod = importlib.reload(main_mod)

    return TestClient(main_mod.app)


# ---------- Helpers ----------
def _last_images_rows(db_path: Path, limit: int = 3) -> list[tuple]:
    con = sqlite3.connect(db_path)
    try:
        return list(
            con.execute(
                """
                SELECT id, session_id, url, ref_used, drift_score, provider, status, latency_ms, created_at
                FROM images
                ORDER BY rowid DESC
                LIMIT ?
                """,
                (limit,),
            )
        )
    finally:
        con.close()


# ---------- Test: happy path end-to-end ----------
def test_session_and_image_generation(tmp_path: Path) -> None:
    db_file = tmp_path / "test.db"

    # 1) Prepare schema
    _init_db(db_file)

    # 2) Real app (stub provider), in-process client
    client = _make_client(db_file)

    # 3) Start a session
    r = client.post("/session/start")
    assert r.status_code == 200, r.text
    session_id = r.json()["session_id"]
    assert session_id

    # 4) Generate an image (stub)
    body: Dict[str, Any] = {
        "session_id": session_id,
        "prompt": "smoke test",
        "size": "512x512",        # accepted by stub / schema; ignored if unused
    }
    rg = client.post("/image/generate", json=body)
    assert rg.status_code == 200, rg.text
    payload = rg.json()
    assert "url" in payload and isinstance(payload["url"], str)
    assert "ref_used" in payload
    # drift_score may be null/None when ref not used or scorer unavailable
    assert "drift_score" in payload

    # 5) Metrics reflect the request
    m = client.get("/metrics")
    assert m.status_code == 200
    metrics = m.json()
    # At least one image generated
    assert metrics.get("images_generated", 0) >= 1

    # 6) Events contain image.generate.ok for our session
    ev = client.get("/events", params={"session_id": session_id})
    assert ev.status_code == 200
    events = ev.json()
    assert any(e["kind"] == "image.generate.ok" for e in events), events

    # 7) Persistence: a row exists in `images` with provider+status
    rows = _last_images_rows(db_file, limit=1)
    assert rows, "expected at least one image row"
    (_img_id, _sid, _url, _ref_used, _drift, _provider, _status, _lat, _created) = rows[0]
    assert _sid == session_id
    assert _provider in ("stub", "comfyui-stub", "stub_images", "stub_provider")
    assert _status == "ok"


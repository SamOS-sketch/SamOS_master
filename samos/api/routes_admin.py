# samos/api/routes_admin.py
from __future__ import annotations

from typing import Dict

from fastapi import APIRouter
from sqlalchemy import func, select

from samos.api.db import SessionLocal, Image as DBImage, Event as DBEvent
from samos.api.metrics import snapshot as metrics_snapshot  # ← our in-process counters

router = APIRouter()


@router.get("/metrics")
def metrics() -> Dict[str, int]:
    """
    Returns a merged metrics view:
      1) Durable DB counts (images/events)
      2) In-process counters (per-provider ok/fail, drift/ref usage, etc.)
    """
    out: Dict[str, int] = {}

    with SessionLocal() as db:
        # Durable image totals
        total_ok = db.execute(
            select(func.count()).select_from(DBImage).where(DBImage.status == "ok")
        ).scalar_one()
        out["images_generated"] = int(total_ok or 0)

        ref_used = db.execute(
            select(func.count()).select_from(DBImage).where(DBImage.ref_used.is_(True))
        ).scalar_one()
        out["image_ref_used_count"] = int(ref_used or 0)

        # Drift breaches recorded as events
        drift_detected = db.execute(
            select(func.count())
            .select_from(DBEvent)
            .where(DBEvent.kind == "image.drift.detected")
        ).scalar_one()
        out["image_drift_detected_count"] = int(drift_detected or 0)

        # Failures are not rows in images table; count from events
        fails = db.execute(
            select(func.count())
            .select_from(DBEvent)
            .where(DBEvent.kind == "image.generate.fail")
        ).scalar_one()
        out["images_failed"] = int(fails or 0)

        # Simple HTTP-ish counters derived from events (best-effort)
        # Count /image/generate calls as ok+fail events
        gen_calls = db.execute(
            select(func.count())
            .select_from(DBEvent)
            .where(DBEvent.kind.in_(("image.generate.ok", "image.generate.fail")))
        ).scalar_one()
        out["http.path:/image/generate"] = int(gen_calls or 0)

        # Count /metrics calls by reading its own event if you emit it (optional, left static)
        # You can swap this for a real middleware counter later.
        # For now, maintain compatibility key:
        out["http.path:/metrics"] = out.get("http.path:/metrics", 1)

    # ---- In-process (per-provider) counters ----
    # e.g., image.ok.comfyui, image.fail.openai, image.ok.stub, etc.
    out.update(metrics_snapshot())

    return out

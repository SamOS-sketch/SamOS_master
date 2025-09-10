# samos/api/routes_images.py
"""
Image routes (Phase A7 – identity lock + drift metrics)

This module defines the /image/generate endpoint.
It wires ImageSkill into FastAPI, logs events, and bumps metrics
without creating circular imports.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from samos.skills.image import ImageSkill
from samos.api.models import ImageGenerateRequest
from samos.api.obs.events import record_event
from samos.config import settings

router = APIRouter()

# single shared skill instance
_skill = ImageSkill(event_logger=None)


@router.post("/image/generate")
def generate_image(req: ImageGenerateRequest):
    """
    Generate an image with identity lock + drift detection (Phase A7).
    """
    try:
        result = _skill.run(
            prompt=req.prompt,
            size=req.size or "1024x1024",
            provider_name=req.provider,
            session_id=req.session_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")

    # Build event payload for observability
    event = {
        "type": f"image.generate.{result.get('status', 'fail')}",
        "session_id": req.session_id,
        "prompt": req.prompt,
        "size": req.size,
        "url": result.get("url"),
        "image_id": result.get("image_id"),
        "meta": result.get("meta", {}),
        "ref_used": result.get("ref_used"),
        "drift_score": result.get("drift_score"),
    }

    # Record event (best-effort)
    try:
        record_event(event["type"], "image generate request", req.session_id, event)
    except Exception:
        pass

    # ---- A7 metrics bump (lazy import to avoid circular dependency) ----
    try:
        from samos.api import main as app_main  # main is already loaded by now
        if event.get("ref_used"):
            app_main._METRICS["image_ref_used_count"] += 1
        drift = event.get("drift_score")
        if isinstance(drift, (int, float)) and drift > settings.DRIFT_THRESHOLD:
            app_main._METRICS["image_drift_detected_count"] += 1
    except Exception:
        # keep metrics non-fatal
        pass

    return result

# samos/api/routes_images.py
"""
Image routes (Phase A8a – identity lock + drift metrics + event consistency)

Defines POST /image/generate. Uses ImageSkill and updates metrics + events in a single place.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from samos.skills.image import ImageSkill
from samos.api.models import ImageGenerateRequest
from samos.api.obs.events import record_event
from samos.config import settings

# Access unified image metrics helper in the same process as /metrics
from samos.api import main as app_main

router = APIRouter()
_skill = ImageSkill(event_logger=None)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/image/generate")
def generate_image(req: ImageGenerateRequest):
    """
    Generate an image with identity lock + drift detection (Phase A8a).
    Ensures:
      - one canonical metrics bump
      - consistent event emission (ok/fail + drift + onebounce)
    """
    try:
        # Model has only prompt + session_id; use sane defaults for others
        result = _skill.run(
            prompt=req.prompt,
            size="1024x1024",
            provider_name=settings.IMAGE_PROVIDER,
            session_id=req.session_id,
        )
    except Exception as e:
        # Count a failed attempt & emit a fail event
        try:
            app_main.bump_image_counters(ok=False)
            record_event(
                "image.generate.fail",
                "image generation error",
                req.session_id,
                {"error": str(e), "ts": _utc_iso()},
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")

    status = str(result.get("status", "fail")).lower()
    ok = status == "ok"

    # Extract meta first (some providers stash flags inside meta)
    meta = dict(result.get("meta") or {})
    meta.setdefault("ts", _utc_iso())
    provider = result.get("provider")
    if provider and "provider" not in meta:
        meta["provider"] = provider

    # Normalize back-compat flags:
    # prefer top-level ref_used/reference_used, else fall back to meta.reference_used/meta.ref_used
    ref_used = bool(
        result.get("ref_used")
        if "ref_used" in result
        else result.get(
            "reference_used",
            meta.get("reference_used", meta.get("ref_used", False)),
        )
    )

    # Drift score (may be None)
    drift_score = result.get("drift_score")

    # --- Event: image.generate.ok/fail ---
    try:
        record_event(
            f"image.generate.{status}",
            "image generate request",
            req.session_id,
            {
                "session_id": req.session_id,
                "prompt": req.prompt,
                "size": "1024x1024",
                "url": result.get("url"),
                "image_id": result.get("image_id"),
                "ref_used": ref_used,
                "drift_score": drift_score,
                "meta": meta,
            },
        )
    except Exception:
        pass

    # --- Metrics: single, unified bump in the API process ---
    try:
        app_main.bump_image_counters(
            ok=ok, ref_used=ref_used, drift_score=drift_score
        )
    except Exception:
        pass

    # --- Event: drift breach → emit once (image.drift.detected + emm.onebounce) ---
    try:
        if isinstance(drift_score, (int, float)) and drift_score > settings.DRIFT_THRESHOLD:
            payload = {
                "session_id": req.session_id,
                "image_id": result.get("image_id"),
                "url": result.get("url"),
                "drift_score": drift_score,
                "threshold": settings.DRIFT_THRESHOLD,
                "meta": meta,
            }
            record_event("image.drift.detected", "drift threshold breached", req.session_id, payload)
            record_event("emm.onebounce", "identity drift breach recorded", req.session_id, payload)
    except Exception:
        pass

    return result

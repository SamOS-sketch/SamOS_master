# samos/api/routes_images.py
"""
Image routes (Phase A8a – identity lock + drift metrics + event consistency)

Defines POST /image/generate. Uses ImageSkill and updates metrics + events in a single place.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

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


def _normalize_file_url(u: str | None) -> str | None:
    """
    Normalize local file URLs, especially on Windows.

    Examples:
      "file://D:\\path\\img.png"   -> "file:///D:/path/img.png"
      "file:///C:/path/img.png"    -> unchanged
      "C:\\path\\img.png"          -> "file:///C:/path/img.png"
    """
    if not u:
        return u
    s = str(u)

    # If it's already a file URL with forward slashes, keep it
    if s.startswith("file:///"):
        return s

    # If it's a 'file://' with backslashes or missing third slash
    if s.lower().startswith("file://"):
        # strip "file://" and normalize
        rest = s[7:].replace("\\", "/")
        # Ensure we have "file:///" + drive colon case (e.g., D:/...)
        if len(rest) >= 2 and rest[1] == ":":
            return f"file:///{rest}"
        # Otherwise, best effort
        return f"file:///{rest.lstrip('/')}"

    # If it's a bare Windows path, convert
    if "\\" in s and ":" in s[:3]:
        drive_fixed = s.replace("\\", "/")
        return f"file:///{drive_fixed}"

    # For anything else, leave as-is
    return s


@router.post("/image/generate")
def generate_image(req: ImageGenerateRequest):
    """
    Generate an image with identity lock + drift detection (Phase A8a).
    Ensures:
      - one canonical metrics bump
      - consistent event emission (ok/fail + drift + onebounce)
    """
    # --- Dev-only test hook: force a runtime failure to exercise fail path ---
    # Send prompt="__FAIL__" to validate images_failed + image.generate.fail.
    if req.prompt == "__FAIL__":
        raise RuntimeError("forced failure for test")

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

    # Normalize URL (especially Windows file paths)
    url_norm = _normalize_file_url(result.get("url"))

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
    # Ensure it's mirrored into meta for downstream consumers
    meta.setdefault("reference_used", ref_used)

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
                "url": url_norm,
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
        app_main.bump_image_counters(ok=ok, ref_used=ref_used, drift_score=drift_score)
    except Exception:
        pass

    # --- Event: drift breach → emit once (image.drift.detected + emm.onebounce) ---
    try:
        if isinstance(drift_score, (int, float)) and drift_score > settings.DRIFT_THRESHOLD:
            payload = {
                "session_id": req.session_id,
                "image_id": result.get("image_id"),
                "url": url_norm,
                "drift_score": drift_score,
                "threshold": settings.DRIFT_THRESHOLD,
                "meta": meta,
            }
            record_event("image.drift.detected", "drift threshold breached", req.session_id, payload)
            record_event("emm.onebounce", "identity drift breach recorded", req.session_id, payload)
    except Exception:
        pass

    # Return result with normalized URL for clients
    if url_norm is not None:
        result = dict(result)
        result["url"] = url_norm
    return result

# samos/api/routes_images.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os, time, json

from samos.api.router import SamRouter
from samos.api.db import get_db, Image as DBImage

router = APIRouter()

# Default mode from env; can be switched via /session/mode
DEFAULT_MODE = os.getenv("DEFAULT_MODE", "sandbox")
ROUTER = SamRouter(DEFAULT_MODE)

class ImageGenerateRequest(BaseModel):
    prompt: str
    recovery_prompt: str | None = None
    fallback_prompt: str | None = None
    reference_path: str | None = None

class ImageGenerateResponse(BaseModel):
    image_id: str
    url: str
    provider: str
    status: str
    meta: dict

@router.post("/session/mode")
def set_mode(mode: str):
    if mode not in ("work", "sandbox"):
        raise HTTPException(400, "mode must be 'work' or 'sandbox'")
    global ROUTER
    ROUTER = SamRouter(mode)
    return {"ok": True, "mode": mode}

@router.post("/image/generate", response_model=ImageGenerateResponse)
def image_generate(req: ImageGenerateRequest, db = Depends(get_db)):
    # Build tiered prompts (always fill all three, reusing the primary if missing)
    tiers = {
        "primary": req.prompt,
        "recovery": req.recovery_prompt or req.prompt,
        "fallback": req.fallback_prompt or req.recovery_prompt or req.prompt,
    }

    # Choose reference image path (env default or request override)
    reference = req.reference_path or os.getenv("REFERENCE_IMAGE_ALPHA_PATH")

    # Call the router (measure latency for the *successful* attempt end-to-end)
    start = time.perf_counter()
    try:
        result = ROUTER.image_generate(tiers, reference_image=reference)
    except Exception as e:
        raise HTTPException(500, f"Image generation failed: {e}")
    latency_ms = int((time.perf_counter() - start) * 1000)

    # Persist to DB (provenance + identity lock flags)
    tier_used = (result.get("meta") or {}).get("tier")
    reference_used = bool((result.get("meta") or {}).get("reference_used"))
    provenance = {
        "provider": result.get("provider"),
        "tier": tier_used,
        "reference_used": reference_used,
        "meta": result.get("meta", {}),
    }

    db_image = DBImage(
        id=result["image_id"],
        session_id=None,                  # optional: wire a real session id if you have it
        prompt=req.prompt,
        provider=result["provider"],
        url=result["url"],
        reference_used=reference_used,
        status=result.get("status", "ok"),
        meta_json=json.dumps(result.get("meta", {})),
        tier=tier_used,
        latency_ms=latency_ms,
        provenance=json.dumps(provenance),
    )
    db.add(db_image)
    db.commit()

    return ImageGenerateResponse(**result)

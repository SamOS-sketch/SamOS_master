# samos/api/routes_images.py
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select, cast, String
from sqlalchemy.orm import Session

from samos.api.db import SessionLocal, Image as DBImage, Event as DBEvent
from samos.api.metrics import inc_ok, inc_fail, inc
from samos.api.paths import resolve_relpath, to_relpath

from samos.providers.image_base import drift_score_for, registry  # provider registry

# Ensure providers self-register on import (side effects)
from samos.providers.comfyui_images import ComfyUIProvider  # noqa: F401
from samos.providers.openai_images import OpenAIProvider    # noqa: F401
from samos.providers.stub import StubProvider               # noqa: F401

router = APIRouter()


# -------- helpers --------

def _provider_chain_from_env() -> List[str]:
    primary = (os.getenv("IMAGE_PROVIDER") or "stub").strip().lower()
    fb = (os.getenv("IMAGE_PROVIDER_FALLBACK") or "").strip().lower()
    raw = [p for p in (primary, *fb.split(":")) if p]
    seen = set()
    chain: List[str] = []
    for p in raw:
        if p not in seen:
            chain.append(p)
            seen.add(p)
    return chain or ["stub"]


def _resolve_provider_class(name: str):
    n = (name or "").strip().lower()

    # Try several registry styles defensively
    try:
        if hasattr(registry, "__getitem__"):
            cls = registry[n]  # type: ignore[index]
            if cls:
                return cls
    except Exception:
        pass
    try:
        if hasattr(registry, "providers"):
            providers = getattr(registry, "providers")
            if isinstance(providers, dict) and n in providers:
                return providers[n]
    except Exception:
        pass
    try:
        if hasattr(registry, "resolve"):
            cls = registry.resolve(n)  # type: ignore[attr-defined]
            if cls:
                return cls
    except Exception:
        pass
    try:
        if hasattr(registry, "get"):
            cls = registry.get(n)  # type: ignore[attr-defined]
            if cls:
                return cls
    except Exception:
        pass

    if n == "comfyui":
        return ComfyUIProvider
    if n == "openai":
        return OpenAIProvider
    if n == "stub":
        return StubProvider

    raise ValueError(f"Unknown provider: {name}")


def _instantiate(name: str):
    cls = _resolve_provider_class(name)
    return cls()


def _emit(db: Session, session_id: Optional[str], kind: str, message: str, meta: Dict):
    evt = DBEvent(
        session_id=session_id,
        kind=kind,
        message=message,
        meta_json=json.dumps(meta or {}),
    )
    db.add(evt)
    db.commit()


def _normalize_result_local_path_for_db(result: Dict) -> Optional[str]:
    """
    Ensure result['local_path'] is stored as POSIX-style RELATIVE path under STATIC_DIR.
    - If provider returned an absolute path under STATIC_DIR -> convert to relative via to_relpath()
    - If already relative -> normalize to POSIX
    - If missing or invalid -> return None (DB will store None)
    """
    raw = (result.get("local_path") or "").strip()
    if not raw:
        return None

    p = Path(raw)
    if p.is_absolute():
        try:
            return to_relpath(p)
        except Exception:
            # If not under STATIC_DIR, keep absolute; serving code handles both.
            return p.as_posix()
    else:
        return Path(raw).as_posix()


def _absolute_path_for_drift(local_path: Optional[str]) -> Optional[str]:
    """
    Return an absolute filesystem path for drift calculation.
    """
    if not local_path:
        return None
    p = Path(local_path)
    if p.is_absolute():
        return str(p)
    try:
        return str(resolve_relpath(local_path))
    except Exception:
        return None


def _persist_ok(
    db: Session,
    session_id: Optional[str],
    prompt: str,
    result: Dict,
    provider_name: str,
    reference_url: Optional[str],
    drift: float,
) -> DBImage:
    local_path_rel_or_abs = _normalize_result_local_path_for_db(result)

    db_img = DBImage(
        session_id=session_id,
        prompt=prompt,
        url=result.get("url"),
        local_path=local_path_rel_or_abs,
        provider=provider_name,
        tier=result.get("meta", {}).get("mode") or result.get("meta", {}).get("tier") or None,
        latency_ms=int(result.get("meta", {}).get("latency_ms") or 0),
        status="ok",
        ref_used=bool(reference_url),
        drift_score=drift,
        meta_json=json.dumps(result.get("meta") or {}),
    )
    db.add(db_img)
    db.commit()
    db.refresh(db_img)
    return db_img


def _get_image_by_id(db: Session, image_id: str) -> Optional[DBImage]:
    """
    Be tolerant of different PK storage styles:
      - TEXT UUID with or without dashes
      - HEX string
      - 16-byte BLOB (uuid.bytes)
      - Vendor-specific types
    """
    # 1) Try plain PK lookup
    obj = db.get(DBImage, image_id)
    if obj:
        return obj

    # 2) Try UUID variations
    try:
        import uuid
        try:
            obj = db.get(DBImage, uuid.UUID(image_id))
            if obj:
                return obj
        except Exception:
            pass
        try:
            obj = db.get(DBImage, uuid.UUID(image_id).bytes)
            if obj:
                return obj
        except Exception:
            pass
    except Exception:
        pass

    # 3) CAST to text
    try:
        obj = db.execute(
            select(DBImage).where(cast(DBImage.id, String) == str(image_id))
        ).scalar_one_or_none()
        if obj:
            return obj
    except Exception:
        pass

    # 4) Final fallback: scan and compare stringified id
    try:
        for img in db.execute(select(DBImage).limit(5000)).scalars().all():
            if str(img.id) == str(image_id):
                return img
    except Exception:
        pass

    return None


# -------- endpoints --------

@router.post("/image/generate")
def image_generate(payload: Dict):
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    session_id: Optional[str] = payload.get("session_id")
    size: str = (payload.get("size") or os.getenv("OPENAI_IMAGE_SIZE") or "1024x1024").strip()
    reference_url: Optional[str] = payload.get("reference_url")
    seed = payload.get("seed")

    chain = _provider_chain_from_env()

    with SessionLocal() as db:
        _emit(db, session_id, "image.route.begin", "begin", {"prompt": prompt, "session_id": session_id})
        _emit(db, session_id, "image.route.policy", "policy", {"providers": chain})

    last_error: Optional[str] = None

    for name in chain:
        provider = _instantiate(name)

        started = time.perf_counter()
        try:
            result: Dict = provider.generate(
                session_id=session_id,
                prompt=prompt,
                size=size,
                reference_image=reference_url,
                seed=seed,
            )
            tried_ms = int((time.perf_counter() - started) * 1000)

            if not result or result.get("status") != "ok":
                raise RuntimeError(f"{name} returned non-ok result")

            # Drift calculation
            drift = 0.0
            try:
                if reference_url and result.get("local_path"):
                    abs_for_drift = _absolute_path_for_drift(result.get("local_path"))
                    if abs_for_drift:
                        drift = float(drift_score_for(reference_url, abs_for_drift))
                    else:
                        drift = 1.0
            except Exception:
                drift = 1.0

            with SessionLocal() as db:
                db_img = _persist_ok(
                    db=db,
                    session_id=session_id,
                    prompt=prompt,
                    result=result,
                    provider_name=name,
                    reference_url=reference_url,
                    drift=drift,
                )
                _emit(db, session_id, "image.generate.ok", "ok", {
                    "id": db_img.id,
                    "provider": name,
                    "latency_ms": result.get("meta", {}).get("latency_ms", tried_ms),
                    "url": db_img.url,
                    "local_path": db_img.local_path,
                    "drift_score": drift,
                })

                inc_ok(name)
                inc("images_generated")
                if reference_url:
                    inc("image.ref.used")

                if reference_url and drift >= float(os.getenv("DRIFT_BREACH_THRESHOLD", "0.85")):
                    _emit(db, session_id, "image.drift.detected", "drift breach", {"score": drift})
                    _emit(db, session_id, "emm.onebounce", "logged", {"score": drift, "provider": name})
                    inc("image.drift.detected")

                return {
                    "id": db_img.id,
                    "url": db_img.url,
                    "provider": name,
                    "local_path": db_img.local_path,
                    "drift_score": drift,
                }

        except Exception as e:
            last_error = str(e)
            with SessionLocal() as db:
                _emit(db, session_id, "image.generate.fail", "fail", {
                    "provider": name,
                    "error": last_error,
                })
                inc_fail(name)
                inc("images_failed")

    raise HTTPException(status_code=502, detail=f"All providers failed: {last_error or 'unknown error'}")


@router.get("/image/{image_id}/file")
def image_file(image_id: str):
    """
    Serve the generated image file:
      1) If local_path exists, stream it (supports rel or abs).
      2) Else if url is file://..., stream resolved path.
      3) Else if url is http(s), redirect.
      4) Else 404.
    """
    with SessionLocal() as db:
        img: Optional[DBImage] = _get_image_by_id(db, image_id)
        if not img:
            raise HTTPException(status_code=404, detail="Image not found")

        # 1) local_path preferred
        p = (getattr(img, "local_path", None) or "").strip()
        if p:
            try:
                abs_path = Path(p)
                if not abs_path.is_absolute():
                    abs_path = resolve_relpath(p)
            except Exception:
                abs_path = None

            if abs_path and abs_path.exists():
                return FileResponse(str(abs_path), media_type="image/png")

        # 2) file:// URL in 'url'
        url = (getattr(img, "url", None) or "").strip()
        if url.startswith("file://"):
            fs_path = os.path.normpath(url.replace("file://", "", 1))
            if os.path.isfile(fs_path):
                return FileResponse(fs_path, media_type="image/png")

        # 3) Redirect to remote URL if present
        if url.startswith("http://") or url.startswith("https://"):
            return RedirectResponse(url)

        # 4) Nothing usable
        raise HTTPException(status_code=404, detail="File not found")


@router.get("/debug/images/recent")
def debug_images_recent(limit: int = 10):
    """
    TEMP: Return recent image rows so we can see how IDs are actually stored.
    Remove after debugging.
    """
    rows = []
    with SessionLocal() as db:
        for img in db.execute(select(DBImage).limit(limit)).scalars().all():
            rows.append({
                "id": img.id,
                "url": getattr(img, "url", None),
                "local_path": getattr(img, "local_path", None),
                "provider": getattr(img, "provider", None),
            })
    return {"count": len(rows), "items": rows}


@router.get("/debug/image/{image_id}/file")
def debug_image_file_strict(image_id: str):
    """
    TEMP: Serve a file by matching the *stringified* id exactly as shown by /debug/images/recent.
    Tries CAST-to-text exact match first, then a full scan (no LIMIT).
    """
    image_id = (image_id or "").strip()

    with SessionLocal() as db:
        img = None

        # 1) CAST-to-text exact match
        try:
            img = db.execute(
                select(DBImage).where(cast(DBImage.id, String) == image_id)
            ).scalar_one_or_none()
        except Exception:
            img = None

        # 2) Full scan, compare stringified ids
        if not img:
            try:
                for row in db.execute(select(DBImage)).scalars():
                    if str(row.id) == image_id:
                        img = row
                        break
            except Exception:
                img = None

        if not img:
            raise HTTPException(status_code=404, detail="Image not found (strict)")

        # Prefer local_path if present
        p = (getattr(img, "local_path", None) or "").strip()
        if p:
            try:
                abs_path = Path(p)
                if not abs_path.is_absolute():
                    abs_path = resolve_relpath(p)
            except Exception:
                abs_path = None

            if abs_path and abs_path.exists():
                return FileResponse(str(abs_path), media_type="image/png")

        # Fallback to file:// URL
        url = (getattr(img, "url", None) or "").strip()
        if url.startswith("file://"):
            fs_path = os.path.normpath(url.replace("file://", "", 1))
            if os.path.isfile(fs_path):
                return FileResponse(fs_path, media_type="image/png")

        # HTTP redirect if remote
        if url.startswith("http://") or url.startswith("https://"):
            return RedirectResponse(url)

        raise HTTPException(status_code=404, detail="File not found (strict)")

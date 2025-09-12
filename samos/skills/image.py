# samos/skills/image.py
import os
import re
import json
import base64
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4
from samos.providers.image_base import compute_drift_score as _compute_drift_score_central

# Try to use the shared API metrics dict; fall back to a local dict.
try:
    from samos.api.main import _METRICS  # global metrics dict
except Exception:  # pragma: no cover
    _METRICS = {"images_generated": 0, "images_failed": 0, "image_drift_detected_count": 0}

# ---------------------------------------------------------------------------
# Provider selection (no external registry dependency)
# ---------------------------------------------------------------------------

def _resolve_provider(provider_name: Optional[str] = None):
    name = (provider_name or os.getenv("IMAGE_PROVIDER", "stub")).lower()
    if name == "openai":
        try:
            from samos.api.image.openai_provider import OpenAIProvider
            return OpenAIProvider()
        except Exception:
            pass  # fall through to stub
    # default stub
    from samos.api.image.stub import StubProvider
    return StubProvider()

# ---------------------------------------------------------------------------
# Drift compute (local, independent of provider)
# ---------------------------------------------------------------------------

def _compute_drift_score_local(
    image_path,
    reference_path,
    method: str = "auto",
    clip_model_name: str = "ViT-B-32",
) -> float:
    """
    Delegates to the canonical drift scorer in providers/image_base.py.
    Kept for backward compatibility so existing callers don't break.
    """
    try:
        return _compute_drift_score_central(
            image_path=image_path,
            reference_path=reference_path,
            method=method,
            clip_model_name=clip_model_name,
        )
    except Exception:
        # Conservative fail-closed: treat as maximum drift if scoring fails
        return 1.0

    image_path = Path(image_path)
    reference_path = Path(reference_path)
    if not image_path.exists() or not reference_path.exists():
        return 1.0

    method = (method or "auto").lower()

    def _clamp01(x: float) -> float:
        return max(0.0, min(1.0, float(x)))

    # CLIP
    def _clip() -> Optional[float]:
        try:
            import torch
            import open_clip
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, _, preprocess = open_clip.create_model_and_transforms(
                clip_model_name, pretrained="laion2b_s34b_b79k"
            )
            model = model.to(device)
            img = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0).to(device)
            ref = preprocess(Image.open(reference_path).convert("RGB")).unsqueeze(0).to(device)
            with torch.no_grad(), torch.cuda.amp.autocast(enabled=(device == "cuda")):
                img_emb = model.encode_image(img)
                ref_emb = model.encode_image(ref)
                img_emb = img_emb / img_emb.norm(dim=-1, keepdim=True)
                ref_emb = ref_emb / ref_emb.norm(dim=-1, keepdim=True)
                sim = (img_emb @ ref_emb.T).squeeze().item()
            sim01 = (sim + 1.0) / 2.0
            return _clamp01(1.0 - sim01)
        except Exception:
            try:
                import torch
                import clip
                device = "cuda" if torch.cuda.is_available() else "cpu"
                model, preprocess = clip.load(clip_model_name, device=device)
                img = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0).to(device)
                ref = preprocess(Image.open(reference_path).convert("RGB")).unsqueeze(0).to(device)
                with torch.no_grad():
                    img_emb = model.encode_image(img)
                    ref_emb = model.encode_image(ref)
                    img_emb = img_emb / img_emb.norm(dim=-1, keepdim=True)
                    ref_emb = ref_emb / ref_emb.norm(dim=-1, keepdim=True)
                    sim = (img_emb @ ref_emb.T).squeeze().item()
                sim01 = (sim + 1.0) / 2.0
                return _clamp01(1.0 - sim01)
            except Exception:
                return None

    # pHash
    def _phash() -> Optional[float]:
        try:
            import imagehash
            from PIL import Image
            img = Image.open(image_path).convert("RGB")
            ref = Image.open(reference_path).convert("RGB")
            h1 = imagehash.phash(img)
            h2 = imagehash.phash(ref)
            dist = h1 - h2
            bit_len = h1.hash.size * h1.hash.size  # usually 64
            return _clamp01(dist / float(bit_len))
        except Exception:
            return None

    # SSIM
    def _ssim() -> Optional[float]:
        try:
            import numpy as np
            from PIL import Image
            from skimage.metrics import structural_similarity as ssim
            img = Image.open(image_path).convert("L").resize((512, 512))
            ref = Image.open(reference_path).convert("L").resize((512, 512))
            img_np = np.array(img)
            ref_np = np.array(ref)
            sim = ssim(img_np, ref_np, data_range=max(1, int(img_np.max()) - int(img_np.min())))
            return _clamp01(1.0 - float(sim))
        except Exception:
            return None

    if method in ("auto", "clip"):
        d = _clip()
        if d is not None:
            return d
        if method == "clip":
            return 1.0
    if method in ("auto", "phash"):
        d = _phash()
        if d is not None:
            return d
        if method == "phash":
            return 1.0
    if method in ("auto", "ssim"):
        d = _ssim()
        if d is not None:
            return d
        if method == "ssim":
            return 1.0
    return 1.0

# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

def _is_data_url(url: str) -> bool:
    return url.startswith("data:image/")

def _decode_data_url(data_url: str) -> bytes:
    m = re.match(r"data:image/(png|jpeg|jpg|webp);base64,(.+)", data_url, re.IGNORECASE)
    if not m:
        raise ValueError("Unsupported data URL format")
    return base64.b64decode(m.group(2))

def _images_dir() -> Path:
    root = Path(os.getenv("SAM_STORAGE_DIR", "D:/SamOS_SSD/samos")).resolve()
    out = root / "images"
    out.mkdir(parents=True, exist_ok=True)
    return out

def _reference_image_path() -> Path:
    return Path(os.getenv("REFERENCE_IMAGE_ALPHA", "D:/SamOS_SSD/samos/outputs/ref_alpha.jpg")).resolve()

class _NoopLogger:
    def info(self, *args, **kwargs): ...
    def warn(self, *args, **kwargs): ...

# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------

class ImageSkill:
    """
    Image generation + persistence + drift detection.

    `event_logger` is optional (duck-typed: .info/.warn). Unknown kwargs ignored.
    """

    def __init__(self, event_logger=None, provider_name: Optional[str] = None, **_: Any):
        self.logger = event_logger or _NoopLogger()
        self.provider = _resolve_provider(provider_name)
        self.images_dir: Path = _images_dir()

    # Flexible wrapper for routers that call .run(...)
    def run(self, *args, **kwargs) -> Dict[str, Any]:
        if args and not kwargs and len(args) == 1:
            req = args[0]
            session_id = getattr(req, "session_id", None) or (req.get("session_id") if isinstance(req, dict) else None)
            prompt = getattr(req, "prompt", None) or (req.get("prompt") if isinstance(req, dict) else None)
            size = getattr(req, "size", "1024x1024") or (req.get("size") if isinstance(req, dict) else "1024x1024")
            reference_image = getattr(req, "reference_image", None) or (req.get("reference_image") if isinstance(req, dict) else None)
            return self.generate(session_id=session_id, prompt=prompt, size=size, reference_image=reference_image)
        return self.generate(
            session_id=kwargs.get("session_id"),
            prompt=kwargs.get("prompt"),
            size=kwargs.get("size", "1024x1024"),
            reference_image=kwargs.get("reference_image"),
        )

    def _materialize_image(self, source: str, image_id: str) -> Path:
        """
        Convert provider output into a local file we can read.
        Supports:
          - data URLs (data:image/*;base64,...)
          - file:// URIs
          - plain local paths
          - stub://image/<id>  → creates a placeholder PNG on disk
        """
        if _is_data_url(source):
            out_path = self.images_dir / f"{image_id}.png"
            out_path.write_bytes(_decode_data_url(source))
            return out_path

        if source.startswith("file://"):
            return Path(source.replace("file://", "", 1)).resolve()

        if source.startswith("stub://"):
            # Create a simple placeholder so downstream steps can run
            out_path = self.images_dir / f"{image_id}.png"
            try:
                from PIL import Image, ImageDraw
                img = Image.new("RGB", (512, 512), (200, 200, 200))
                d = ImageDraw.Draw(img)
                d.text((20, 20), "stub image", fill=(0, 0, 0))
                img.save(out_path)
            except Exception:
                out_path.write_bytes(
                    base64.b64decode(
                        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
                    )
                )
            return out_path

        p = Path(source)
        if p.exists():
            return p.resolve()

        raise FileNotFoundError(f"Image path not found or unsupported URL: {source}")

    def _save_sidecar(self, image_id: str, data: Dict[str, Any]) -> Path:
        sidecar = self.images_dir / f"{image_id}.json"
        sidecar.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return sidecar

    def generate(
        self,
        session_id: Optional[str],
        prompt: str,
        size: str = "1024x1024",
        reference_image: Optional[str] = None,
    ) -> Dict[str, Any]:
        # 1) Generate via provider (pass tier if required; fallback if not supported)
        tier = os.getenv("IMAGE_TIER", "base")
        try:
            result = self.provider.generate(
                session_id=session_id,
                prompt=prompt,
                size=size,
                reference_image=reference_image or str(_reference_image_path()),
                tier=tier,
            )
        except TypeError:
            # Provider doesn't accept `tier`
            result = self.provider.generate(
                session_id=session_id,
                prompt=prompt,
                size=size,
                reference_image=reference_image or str(_reference_image_path()),
            )
        except Exception as e:
            _METRICS["images_failed"] = _METRICS.get("images_failed", 0) + 1
            if hasattr(self.logger, "warn"):
                self.logger.warn("image.generate.error", {"error": str(e), "prompt": prompt})
            raise

        status = result.get("status", "fail")
        url_or_path = result.get("url")
        provider_name = result.get("provider", "unknown")
        image_id = result.get("image_id") or uuid4().hex
        reference_used = result.get("reference_used")
        meta = result.get("meta", {})

        if status != "ok":
            _METRICS["images_failed"] = _METRICS.get("images_failed", 0) + 1
            if hasattr(self.logger, "warn"):
                self.logger.warn("image.generate.fail", {"provider": provider_name, "prompt": prompt, "meta": meta})
            return {"status": "fail", "provider": provider_name, "message": "Provider returned non-ok status", "meta": meta}

        # 2) Ensure local file
        local_path: Path = self._materialize_image(url_or_path, image_id)

        # 3) Drift detection (local)
        ref_path = _reference_image_path()
        drift_score = 0.0
        try:
            if ref_path.exists():
                method = os.getenv("DRIFT_METHOD", "auto")
                drift_score = _compute_drift_score_local(local_path, ref_path, method=method)
            else:
                if hasattr(self.logger, "warn"):
                    self.logger.warn("image.drift.noref", {"reference_path": str(ref_path)})
        except Exception as e:
            drift_score = 1.0
            if hasattr(self.logger, "warn"):
                self.logger.warn("image.drift.error", {"error": str(e)})

        # 4) Sidecar persistence (until DB schema is aligned)
        file_url = f"file://{local_path}"
        sidecar_data = {
            "image_id": image_id,
            "url": file_url,
            "prompt": prompt,
            "provider": provider_name,
            "reference_used": True if reference_used is None else bool(reference_used),
            "drift_score": float(drift_score),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "meta": meta,
        }
        self._save_sidecar(image_id, sidecar_data)

        # 5) Threshold, metrics, events
        try:
            threshold = float(os.getenv("DRIFT_THRESHOLD", "0.35"))
        except Exception:
            threshold = 0.35

        if hasattr(self.logger, "info"):
            self.logger.info("image.generated", {
                "image_id": image_id,
                "url": file_url,
                "provider": provider_name,
                "prompt": prompt,
                "drift_score": drift_score,
                "threshold": threshold,
                "reference_used": sidecar_data["reference_used"],
            })

        _METRICS["images_generated"] = _METRICS.get("images_generated", 0) + 1

        if drift_score > threshold:
            _METRICS["image_drift_detected_count"] = _METRICS.get("image_drift_detected_count", 0) + 1

            if hasattr(self.logger, "info"):
                self.logger.info("image.drift.detected", {
                    "image_id": image_id,
                    "url": file_url,
                    "drift_score": drift_score,
                    "threshold": threshold,
                })
                self.logger.info("emm.onebounce", {
                    "image_id": image_id,
                    "reason": "drift_threshold_breached",
                    "drift_score": drift_score,
                    "threshold": threshold,
                })

        # 6) Return payload (NOTE: return 'url', not 'path', to match router expectations)
        return {
            "status": "ok",
            "image_id": image_id,
            "url": file_url,
            "provider": provider_name,
            "prompt": prompt,
            "drift_score": drift_score,
            "meta": meta,
        }


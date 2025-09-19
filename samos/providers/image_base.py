# samos/providers/image_base.py
from __future__ import annotations

import os
import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional

# -------- Drift config from environment (with validation) --------
_ALLOWED_METHODS = {"auto", "clip", "phash", "ssim"}

_env_method = (os.getenv("DRIFT_METHOD", "auto") or "auto").lower()
DRIFT_METHOD = _env_method if _env_method in _ALLOWED_METHODS else "auto"

# Threshold is read by the API layer; we keep it here for convenience
try:
    DRIFT_THRESHOLD: float = float(os.getenv("DRIFT_THRESHOLD", "0.35"))
except ValueError:
    DRIFT_THRESHOLD = 0.35

# Optional: model name override for CLIP
CLIP_MODEL_NAME = os.getenv("DRIFT_CLIP_MODEL", "ViT-B-32")


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def compute_drift_score(
    image_path: Path | str,
    reference_path: Path | str,
    method: str = DRIFT_METHOD,
    clip_model_name: str = CLIP_MODEL_NAME,
) -> Optional[float]:
    """
    Compute visual drift between `image_path` and `reference_path`.

    Returns:
      float in [0, 1] where 0 = identical (no drift), 1 = maximally different,
      or None if drift couldn't be computed (no files / missing deps / errors).

    A8b 'auto' preference order (fast-first):
      1) pHash (perceptual hash)
      2) SSIM (grayscale structural similarity)
      3) CLIP embeddings (heavy; only if explicitly requested or previous fallbacks missing)
    """
    # --- basic guards & light deps ---
    try:
        from PIL import Image  # pillow
    except Exception:
        return None

    src = Path(str(image_path)) if image_path else None
    ref = Path(str(reference_path)) if reference_path else None
    if not src or not ref or not src.exists() or not ref.exists():
        return None

    mode = (method or "auto").lower()
    if mode not in _ALLOWED_METHODS:
        mode = "auto"

    # --- pHash (fast, low-dep) ---
    def _phash() -> Optional[float]:
        try:
            import imagehash
            h1 = imagehash.phash(Image.open(ref).convert("RGB"))
            h2 = imagehash.phash(Image.open(src).convert("RGB"))
            # Hamming distance normalized by bit length (typically 64)
            dist = (h1 - h2)
            bit_len = int(h1.hash.size)  # already N*N (e.g., 64) – do not square
            if bit_len <= 0:
                return None
            return _clamp01(dist / float(bit_len))
        except Exception:
            return None

    # --- SSIM (still light; numpy/skimage) ---
    def _ssim() -> Optional[float]:
        try:
            import numpy as np
            from skimage.metrics import structural_similarity as ssim
            img = Image.open(src).convert("L").resize((512, 512))
            ref_img = Image.open(ref).convert("L").resize((512, 512))
            a = np.array(img)
            b = np.array(ref_img)
            data_range = max(1, int(a.max()) - int(a.min()))
            sim = float(ssim(a, b, data_range=data_range))
            return _clamp01(1.0 - sim)  # invert to drift
        except Exception:
            return None

    # --- CLIP (heavy; only if asked or fallbacks failed) ---
    def _clip() -> Optional[float]:
        # Prefer open_clip; fallback to clip if available
        try:
            import torch
            import open_clip
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, _, preprocess = open_clip.create_model_and_transforms(
                clip_model_name, pretrained="laion2b_s34b_b79k"
            )
            model = model.to(device)
            x = preprocess(Image.open(src).convert("RGB")).unsqueeze(0).to(device)
            y = preprocess(Image.open(ref).convert("RGB")).unsqueeze(0).to(device)
            with torch.no_grad():
                a = model.encode_image(x)
                b = model.encode_image(y)
                a = a / a.norm(dim=-1, keepdim=True)
                b = b / b.norm(dim=-1, keepdim=True)
                sim = (a @ b.T).squeeze().item()  # [-1,1]
            return _clamp01(1.0 - ((sim + 1.0) / 2.0))
        except Exception:
            try:
                import torch
                import clip
                device = "cuda" if torch.cuda.is_available() else "cpu"
                model, preprocess = clip.load(clip_model_name, device=device)
                x = preprocess(Image.open(src).convert("RGB")).unsqueeze(0).to(device)
                y = preprocess(Image.open(ref).convert("RGB")).unsqueeze(0).to(device)
                with torch.no_grad():
                    a = model.encode_image(x)
                    b = model.encode_image(y)
                    a = a / a.norm(dim=-1, keepdim=True)
                    b = b / b.norm(dim=-1, keepdim=True)
                    sim = (a @ b.T).squeeze().item()
                return _clamp01(1.0 - ((sim + 1.0) / 2.0))
            except Exception:
                return None

    # ---- Execution order ----
    if mode == "phash":
        return _phash()
    if mode == "ssim":
        return _ssim()
    if mode == "clip":
        return _clip()

    # auto: phash → ssim → clip
    return _phash() or _ssim() or _clip()


# ---------- Provider Base & Registry ----------

class ImageProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(
        self,
        session_id: Optional[str],
        prompt: str,
        size: str,
        reference_image: Optional[str],
    ) -> Dict[str, Any]:
        """
        Return dict with keys at least:
          - url (str)      : an image URL or data URL
          - provider (str) : provider name
          - image_id (str) : unique id
          - reference_used (str|None)
          - status (str)   : "ok" | "fail"
          - meta (dict)    : any useful extras (e.g., prompt_hash)
        """
        raise NotImplementedError

    # Delegate to canonical drift scorer (Optional[float] for A8b semantics)
    def compute_drift_score(
        self,
        image_path: Path | str,
        reference_path: Path | str,
        method: str = DRIFT_METHOD,
        clip_model_name: str = CLIP_MODEL_NAME,
    ) -> Optional[float]:
        try:
            return compute_drift_score(
                image_path=image_path,
                reference_path=reference_path,
                method=method,
                clip_model_name=clip_model_name,
            )
        except Exception:
            return None


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, type[ImageProvider]] = {}

    def register(self, provider_cls: type[ImageProvider]):
        name = getattr(provider_cls, "name", None)
        if not name:
            raise ValueError("Provider class must define a 'name' attribute")
        self._providers[name] = provider_cls
        return provider_cls

    def create(self, name: str) -> ImageProvider:
        if name not in self._providers:
            raise ValueError(
                f"Unknown image provider '{name}'. Registered: {sorted(self._providers.keys())}"
            )
        return self._providers[name]()

    def available(self) -> list[str]:
        return sorted(self._providers.keys())


registry = ProviderRegistry()

# ---- Drift scoring shim ----

def drift_score_for(reference_url: Optional[str], local_path: Optional[str]) -> float:
    """
    Centralized image drift scoring.
    Return 0.0..1.0 (higher = more drift).
    Falls back to 1.0 if scoring cannot be computed.
    """
    if not reference_url or not local_path:
        return 0.0
    try:
        # placeholder: real drift scoring can use CLIP/SSIM/etc
        # import your scorer here if available
        return 0.5  # neutral mid-point until real scorer is wired
    except Exception:
        return 1.0


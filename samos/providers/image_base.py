# providers/image_base.py
import os
import time
import base64
import hashlib
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path

# -------- Drift config from environment (with validation) --------
_ALLOWED_METHODS = {"auto", "clip", "phash", "ssim"}

_env_method = (os.getenv("DRIFT_METHOD", "auto") or "auto").lower()
DRIFT_METHOD = _env_method if _env_method in _ALLOWED_METHODS else "auto"

try:
    DRIFT_THRESHOLD: float = float(os.getenv("DRIFT_THRESHOLD", "0.35"))
except ValueError:
    DRIFT_THRESHOLD = 0.35

# Optional: model name override for CLIP
CLIP_MODEL_NAME = os.getenv("DRIFT_CLIP_MODEL", "ViT-B-32")


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# -------- Canonical drift scorer (Phase A8a) --------
def compute_drift_score(
    image_path: Path | str,
    reference_path: Path | str,
    method: str = DRIFT_METHOD,
    clip_model_name: str = CLIP_MODEL_NAME,
) -> float:
    """
    Compute visual drift between `image_path` and `reference_path`.

    Returns a float in [0, 1], where:
      0.0 = identical / no drift
      1.0 = completely different / maximum drift

    Preference order when method="auto":
      1) CLIP embeddings (open_clip → clip)  [GPU if available]
      2) pHash (perceptual hash)
      3) SSIM (grayscale structural similarity)
      4) Stub fallback (returns 1.0)
    """
    # Local import to avoid hard dependency if not installed
    try:
        from PIL import Image
    except Exception:
        return 1.0  # If PIL isn't available, safest is to treat as drifted

    # Normalize inputs
    image_path = Path(image_path)
    reference_path = Path(reference_path)
    if not image_path.exists() or not reference_path.exists():
        return 1.0

    method = (method or "auto").lower()
    if method not in _ALLOWED_METHODS:
        method = "auto"

    def _clamp01(x: float) -> float:
        return max(0.0, min(1.0, float(x)))

    # --- Option 1: CLIP embeddings (preferred) ---
    def _clip_drift() -> Optional[float]:
        # Try open_clip (actively maintained)
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
                sim = (img_emb @ ref_emb.T).squeeze().item()  # cosine similarity [-1, 1]

            sim01 = (sim + 1.0) / 2.0  # [-1,1] -> [0,1]
            drift = 1.0 - sim01        # invert to drift
            return _clamp01(drift)
        except Exception:
            # Try OpenAI's clip package as secondary path
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
                drift = 1.0 - sim01
                return _clamp01(drift)
            except Exception:
                return None

    # --- Option 2: pHash (perceptual hash) ---
    def _phash_drift() -> Optional[float]:
        try:
            import imagehash
            img = Image.open(image_path).convert("RGB")
            ref = Image.open(reference_path).convert("RGB")
            h1 = imagehash.phash(img)
            h2 = imagehash.phash(ref)
            # Hamming distance (0..64 typically for 8x8 phash)
            dist = h1 - h2
            # h1.hash is an NxN boolean matrix. .size is N*N already (e.g. 64). Do NOT square it.
            bit_len = int(h1.hash.size)
            if bit_len <= 0:
                return None
            drift = dist / float(bit_len)
            return _clamp01(drift)
        except Exception:
            return None

    # --- Option 3: SSIM baseline ---
    def _ssim_drift() -> Optional[float]:
        try:
            import numpy as np
            from skimage.metrics import structural_similarity as ssim
            img = Image.open(image_path).convert("L").resize((512, 512))
            ref = Image.open(reference_path).convert("L").resize((512, 512))
            img_np = np.array(img)
            ref_np = np.array(ref)
            # data_range should be the value range of the image dtype
            data_range = max(1, int(img_np.max()) - int(img_np.min()))
            sim = ssim(img_np, ref_np, data_range=data_range)
            drift = 1.0 - float(sim)  # SSIM ∈ [0,1] → drift
            return _clamp01(drift)
        except Exception:
            return None

    # Execute preference order (or explicit choice)
    if method in ("auto", "clip"):
        d = _clip_drift()
        if d is not None:
            return d
        if method == "clip":
            return 1.0  # explicit request but CLIP unavailable

    if method in ("auto", "phash"):
        d = _phash_drift()
        if d is not None:
            return d
        if method == "phash":
            return 1.0

    if method in ("auto", "ssim"):
        d = _ssim_drift()
        if d is not None:
            return d
        if method == "ssim":
            return 1.0

    # Ultimate stub fallback (should rarely happen)
    return 1.0


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

    # --- Delegate to the canonical drift scorer (keeps subclasses simple) ---
    def compute_drift_score(
        self,
        image_path: Path | str,
        reference_path: Path | str,
        method: str = DRIFT_METHOD,
        clip_model_name: str = CLIP_MODEL_NAME,
    ) -> float:
        try:
            return compute_drift_score(
                image_path=image_path,
                reference_path=reference_path,
                method=method,
                clip_model_name=clip_model_name,
            )
        except Exception:
            # Conservative fail-closed: treat as maximum drift if scoring fails
            return 1.0


class ProviderRegistry:
    def __init__(self):
        self._providers = {}

    def register(self, provider_cls):
        name = provider_cls.name
        self._providers[name] = provider_cls
        return provider_cls

    def create(self, name: str) -> ImageProvider:
        if name not in self._providers:
            raise ValueError(f"Unknown image provider '{name}'. Registered: {list(self._providers.keys())}")
        return self._providers[name]()

    def available(self):
        return sorted(self._providers.keys())


registry = ProviderRegistry()

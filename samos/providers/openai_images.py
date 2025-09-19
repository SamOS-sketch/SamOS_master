# samos/providers/openai_images.py
from __future__ import annotations

import io
import os
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from PIL import Image

try:
    from openai import OpenAI  # openai>=1.0
except Exception as e:
    OpenAI = None  # handled at call-time

from .image_base import ImageProvider, prompt_hash, registry


def _outputs_dir() -> str:
    d = os.path.abspath(os.getenv("OUTPUTS_DIR", "outputs"))
    os.makedirs(d, exist_ok=True)
    return d


def _persist_png(image_bytes: bytes) -> Tuple[str, str, str]:
    """
    Save bytes as PNG under OUTPUTS_DIR.
    Returns (image_id, local_path, file_url).
    """
    img = Image.open(io.BytesIO(image_bytes))
    img.load()
    image_id = uuid.uuid4().hex
    local_path = os.path.join(_outputs_dir(), f"{image_id}.png")
    img.save(local_path, format="PNG")
    return image_id, local_path, f"file://{local_path}"


def _client() -> Any:
    if OpenAI is None:
        raise RuntimeError("OpenAI SDK not available. Install with: pip install openai>=1.0.0")
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        organization=os.getenv("OPENAI_ORG") or None,
        project=os.getenv("OPENAI_PROJECT") or None,
    )


def _model() -> str:
    return os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")


def _size(default_from_call: Optional[str]) -> str:
    return (default_from_call or os.getenv("OPENAI_IMAGE_SIZE") or "1024x1024").strip()


@registry.register
class OpenAIProvider(ImageProvider):
    """
    OpenAI Images provider (gpt-image-1).
    - Persists the image to OUTPUTS_DIR
    - Returns file:// URL and local_path
    - Conforms to ImageProvider.generate(...) return structure used by routing
    """

    name = "openai"

    def generate(
        self,
        session_id: Optional[str],
        prompt: str,
        size: str,
        reference_image: Optional[str],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        client = _client()
        model = _model()
        req_size = _size(size)

        # Minimal reference handling: hint the model with text.
        # (If you later want true image+text conditioning, move to edits/variations APIs.)
        full_prompt = prompt
        if reference_image:
            full_prompt = f"{prompt}\n(Reference image: {reference_image})"

        try:
            resp = client.images.generate(
                model=model,
                prompt=full_prompt,
                size=req_size,
                n=1,
            )
            # SDK returns base64 JSON
            b64 = resp.data[0].b64_json
            img_bytes = self._b64_to_bytes(b64)

            image_id, local_path, file_url = _persist_png(img_bytes)
            latency_ms = int((time.perf_counter() - started) * 1000)

            return {
                "url": file_url,
                "local_path": local_path,
                "provider": self.name,
                "image_id": image_id,
                "reference_used": bool(reference_image),
                "status": "ok",
                "meta": {
                    "latency_ms": latency_ms,
                    "prompt_hash": prompt_hash(prompt),
                    "size": req_size,
                    "session_id": session_id,
                    "engine": model,
                },
            }
        except Exception as e:
            # Let the router handle fallback
            raise RuntimeError(f"OpenAI image error: {e}") from e

    # --- helpers ---
    @staticmethod
    def _b64_to_bytes(s: str) -> bytes:
        import base64
        return base64.b64decode(s)

# samos/providers/stub.py
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from PIL import Image, ImageDraw  # pillow required

from samos.config import settings
from samos.providers.image_base import ImageProvider, registry, prompt_hash


def _outputs_dir() -> Path:
    """
    Use the same storage root the API prepares on startup:
    <settings.SAM_STORAGE_DIR>/outputs
    """
    root = Path(getattr(settings, "SAM_STORAGE_DIR", "storage")).resolve()
    out = root / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    return out


@registry.register
class StubProvider(ImageProvider):
    name = "stub"

    def generate(
        self,
        session_id: Optional[str],
        prompt: str,
        size: str = "1024x1024",
        reference_image: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate a simple placeholder PNG and put it in the shared outputs dir.
        Return both `url` (file://...) and `local_path` so /image/{id}/file can
        resolve the file consistently across providers.
        """
        t0 = time.time()

        # --- parse size ---
        w, h = 1024, 1024
        try:
            if isinstance(size, str) and "x" in size.lower():
                sx, sy = size.lower().split("x", 1)
                w, h = int(sx.strip()), int(sy.strip())
        except Exception:
            # fall back silently
            w, h = 1024, 1024

        # --- draw simple card with prompt hash ---
        img = Image.new("RGB", (w, h), (240, 240, 240))
        draw = ImageDraw.Draw(img)
        ph = prompt_hash(prompt)
        draw.text((20, 20), f"SamOS Stub\n{ph}", fill=(40, 40, 40))

        # --- path & write ---
        image_id = uuid.uuid4().hex  # hex id (no dashes)
        out_dir = _outputs_dir()
        file_name = f"{image_id}.png"
        path = (out_dir / file_name).resolve()
        img.save(path, format="PNG")

        # --- response fields ---
        latency_ms = int((time.time() - t0) * 1000)
        file_url = path.as_uri()
        local_path = str(path)

        # Note: include both top-level keys and meta mirrors
        meta = {
            "prompt_hash": ph,
            "size": f"{w}x{h}",
            "tier": "primary",
            "latency_ms": latency_ms,
            "local_path": local_path,
            "content_type": "image/png",
        }

        return {
            "url": file_url,                 # e.g., file:///C:/.../outputs/<id>.png
            "local_path": local_path,        # e.g., C:\...\outputs\<id>.png
            "provider": self.name,
            "image_id": image_id,
            "reference_used": bool(reference_image),
            "status": "ok",
            "content_type": "image/png",
            "meta": meta,
        }


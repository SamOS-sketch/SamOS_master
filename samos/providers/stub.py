# samos/providers/stub.py
from __future__ import annotations
import io, time, uuid
from pathlib import Path
from typing import Dict, Any, Optional

from PIL import Image, ImageDraw  # pillow required
from samos.providers.image_base import ImageProvider, registry, prompt_hash

OUTPUT_DIR = Path("./outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@registry.register
class StubProvider(ImageProvider):
    name = "stub"

    def generate(
        self,
        session_id: Optional[str],
        prompt: str,
        size: str = "1024x1024",
        reference_image: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Simple placeholder image with prompt hash
        t0 = time.time()
        w, h = (1024, 1024)
        try:
            if "x" in size:
                parts = size.lower().split("x")
                w = int(parts[0].strip()); h = int(parts[1].strip())
        except Exception:
            pass

        img = Image.new("RGB", (w, h), (240, 240, 240))
        draw = ImageDraw.Draw(img)
        ph = prompt_hash(prompt)
        draw.text((20, 20), f"SamOS Stub\n{ph}", fill=(40, 40, 40))

        image_id = str(uuid.uuid4()).replace("-", "")
        path = OUTPUT_DIR / f"stub_{image_id}.png"
        img.save(path, format="PNG")

        latency_ms = int((time.time() - t0) * 1000)

        # Make a file:// URL
        url = path.resolve().as_uri()

        return {
            "url": url,
            "provider": self.name,
            "image_id": image_id,
            "reference_used": bool(reference_image),
            "status": "ok",
            "meta": {
                "prompt_hash": ph,
                "size": f"{w}x{h}",
                "tier": "primary",
                "latency_ms": latency_ms,
            },
        }

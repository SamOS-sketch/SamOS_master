# samos/providers/openai_images.py
from __future__ import annotations

import os
import uuid
import time
import base64
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from .image_base import ImageProvider, prompt_hash, registry

# --- SSD outputs setup (one source of truth) ---
from samos.core.config import STORAGE_DIR
from samos.runtime.event_logger import log_event

OUTPUTS_PATH: Path = STORAGE_DIR / "outputs"
OUTPUTS_PATH.mkdir(parents=True, exist_ok=True)

def _new_filename(ext: str = ".png") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return OUTPUTS_PATH / f"img_{ts}{ext}"
# --- end SSD block ---


@registry.register
class OpenAIProvider(ImageProvider):
    name = "openai"

    def __init__(self):
        # Relies on OPENAI_API_KEY in the environment
        self.client = OpenAI()

    def generate(
        self,
        session_id: Optional[str],
        prompt: str,
        size: str,
        reference_image: Optional[str],
    ) -> Dict[str, Any]:
        start = time.time()

        # Light-touch reference hinting (text only)
        if reference_image:
            prompt = f"{prompt}\n\nReference hint: {reference_image}"

        try:
            resp = self.client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size=size,
            )
            b64 = resp.data[0].b64_json
            image_bytes = base64.b64decode(b64)

            # ---- Save to SSD outputs ----
            image_id = str(uuid.uuid4())
            out_path = _new_filename(".png")
            with out_path.open("wb") as f:
                f.write(image_bytes)

            # Log event with storage metadata
            log_event(
                "image_saved",
                {
                    "path": str(out_path),
                    "provider": self.name,
                    "storage.path": str(OUTPUTS_PATH),
                    "image_id": image_id,
                },
            )

            latency_ms = int((time.time() - start) * 1000)

            return {
                "url": str(out_path.resolve()),
                "provider": self.name,
                "image_id": image_id,
                "reference_used": reference_image,
                "status": "ok",
                "meta": {
                    "latency_ms": latency_ms,
                    "prompt_hash": prompt_hash(prompt),
                    "size": size,
                    "session_id": session_id,
                },
            }

        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            return {
                "url": "",
                "provider": self.name,
                "image_id": "",
                "reference_used": reference_image,
                "status": "fail",
                "error": str(e),
                "meta": {
                    "latency_ms": latency_ms,
                    "prompt_hash": prompt_hash(prompt),
                    "size": size,
                    "session_id": session_id,
                },
            }

# providers/comfyui_images.py
import uuid
import time
from typing import Dict, Any, Optional

from .image_base import ImageProvider, prompt_hash, registry


@registry.register
class ComfyUIProvider(ImageProvider):
    name = "comfyui"

    def generate(
        self,
        session_id: Optional[str],
        prompt: str,
        size: str,
        reference_image: Optional[str],
    ) -> Dict[str, Any]:
        start = time.time()
        image_id = str(uuid.uuid4())
        latency_ms = int((time.time() - start) * 1000)
        # Stub URL proves routing; swap for real ComfyUI endpoint later.
        return {
            "url": f"stub://comfyui/{image_id}",
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

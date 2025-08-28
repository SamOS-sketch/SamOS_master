import os, uuid
from .base import BaseImage


class OpenAIImages(BaseImage):
    name = "openai"
    supports_reference = False  # no IP-Adapter; we use prompt injection later

    def generate(
        self, prompt: str, reference_image: str | None, tier: str, **kw
    ) -> dict:
        if os.getenv("OPENAI_IMG_SIMULATE_DOWN", "false").lower() == "true":
            raise RuntimeError("OpenAI Images simulated down")
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY missing")

        img_id = str(uuid.uuid4())
        # Dry-run success (no external call today)
        return {
            "image_id": img_id,
            "url": f"openai://image/{img_id}",
            "provider": self.name,
            "status": "ok",
            "meta": {
                "prompt": prompt,
                "tier": tier,
                "reference_used": False,
                "note": "Dry-run shim. Replace with real OpenAI Images call.",
            },
        }

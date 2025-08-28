import os, uuid
from .base import BaseImage


class StabilityImages(BaseImage):
    name = "stability_api"
    supports_reference = False  # flip True if you wire style/ref later

    def generate(
        self, prompt: str, reference_image: str | None, tier: str, **kw
    ) -> dict:
        if os.getenv("STABILITY_SIMULATE_DOWN", "false").lower() == "true":
            raise RuntimeError("Stability simulated down")
        if not os.getenv("STABILITY_API_KEY"):
            raise RuntimeError("STABILITY_API_KEY missing")

        img_id = str(uuid.uuid4())
        # Dry-run success (no external call today)
        return {
            "image_id": img_id,
            "url": f"stability://image/{img_id}",
            "provider": self.name,
            "status": "ok",
            "meta": {
                "prompt": prompt,
                "tier": tier,
                "reference_used": False,
                "note": "Dry-run shim. Replace with real Stability call.",
            },
        }

import os

from .base import BaseImage


class ComfyUIImages(BaseImage):
    name = "comfyui"
    supports_reference = True  # IP-Adapter expected when GPU is ready

    def generate(
        self, prompt: str, reference_image: str | None, tier: str, **kw
    ) -> dict:
        # For now we simulate "down" (no GPU today)
        if os.getenv("COMFYUI_SIMULATE_DOWN", "true").lower() == "true":
            raise RuntimeError("ComfyUI simulated down (no GPU today)")
        # When hardware is available, implement HTTP call to ComfyUI workflow here
        raise NotImplementedError("Wire ComfyUI HTTP workflow when GPU is available")

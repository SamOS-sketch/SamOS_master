from .base import BaseImage


class LocalDiffusionImages(BaseImage):
    name = "local_diffusion"
    supports_reference = True

    def generate(
        self, prompt: str, reference_image: str | None, tier: str, **kw
    ) -> dict:
        raise NotImplementedError("Implement torch pipeline once GPU arrives")

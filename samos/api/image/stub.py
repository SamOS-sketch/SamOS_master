import uuid

from .base import BaseImage


class StubProvider(BaseImage):
    name = "stub"
    supports_reference = False

    def generate(
        self, prompt: str, reference_image: str | None, tier: str, **kw
    ) -> dict:
        if isinstance(prompt, str) and "force_fail" in prompt.lower():
            raise RuntimeError("StubProvider forced failure for testing")
        image_id = str(uuid.uuid4())
        return {
            "image_id": image_id,
            "url": f"stub://image/{image_id}",
            "provider": self.name,
            "status": "ok",
            "meta": {
                "prompt": prompt,
                "tier": tier,
                "reference_used": bool(reference_image),
            },
        }

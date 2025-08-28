class BaseImage:
    name = "base"
    supports_reference = False  # providers with IP-Adapter will set True

    def generate(self, prompt: str, reference_image: str | None, tier: str, **kw) -> dict:
        raise NotImplementedError


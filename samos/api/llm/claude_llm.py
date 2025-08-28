from .base import BaseLLM


class ClaudeLLM(BaseLLM):
    name = "claude"

    def generate(self, prompt: str, **kw) -> dict:
        # Simulate unavailable today to test fallback later
        raise RuntimeError("Claude simulated down (no key configured)")

from typing import Optional, Tuple
from .openai_client import OpenAIClient, OpenAIConfig

class LLMService:
    """
    Thin provider wrapper. Keeps skills/router API unchanged.

    Usage:
        llm = LLMService(provider="openai")  # or "local"/"echo" for stub
        text, latency_ms = llm.generate("Hello", system_prompt="You are helpful.")
    """

    def __init__(self, provider: str = "openai"):
        self.provider = provider
        if provider == "openai":
            self.client = OpenAIClient(OpenAIConfig())
        elif provider in ("local", "echo"):
            self.client = None
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def generate(
        self,
        user_text: str,
        system_prompt: Optional[str] = None,
    ) -> Tuple[str, Optional[int]]:
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": user_text})

        if self.provider == "openai":
            result = self.client.chat(msgs)
            if not result["ok"]:
                raise RuntimeError(f"llm.fail: {result['error']}")
            return result["text"], result.get("latency_ms")

        # fallback stub
        return f"[stub] {user_text}", None

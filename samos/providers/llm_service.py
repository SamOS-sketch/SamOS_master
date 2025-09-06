from typing import Optional, Tuple
import os
from .openai_client import OpenAIClient, OpenAIConfig

class LLMService:
    """
    Thin provider wrapper. Keeps skills/router API unchanged.

    Usage:
        llm = LLMService()                  # defaults to env SAM_PROVIDER or "openai"
        llm = LLMService(provider="openai") # force OpenAI
        llm = LLMService(provider="local")  # stub/echo mode
    """

    def __init__(self, provider: Optional[str] = None):
        # Default priority: explicit arg > env > "openai"
        self.provider = provider or os.getenv("SAM_PROVIDER", "openai")

        if self.provider == "openai":
            self.client = OpenAIClient(OpenAIConfig())
        elif self.provider in ("local", "echo"):
            self.client = None
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

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

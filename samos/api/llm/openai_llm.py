import os
from .base import BaseLLM


class OpenAILLM(BaseLLM):
    name = "openai"

    def generate(self, prompt: str, **kw) -> dict:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY missing")
        return {"completion_id": "openai:dry-run", "text": "[openai llm placeholder]"}

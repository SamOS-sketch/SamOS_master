import os
from typing import Tuple, Optional
from samos.providers.llm_service import LLMService

# Singleton holder
_LLM_SINGLETON: Optional[LLMService] = None

def _provider_from_env() -> str:
    # Default stays echo unless you set SAM_PROVIDER=openai
    return os.getenv("SAM_PROVIDER", "echo").lower()

def get_llm() -> LLMService:
    global _LLM_SINGLETON
    if _LLM_SINGLETON is None:
        prov = _provider_from_env()
        # Map "echo" to our stub mode
        provider = "openai" if prov == "openai" else "local"
        _LLM_SINGLETON = LLMService(provider=provider)
    return _LLM_SINGLETON

def llm_generate(user_text: str, system_prompt: Optional[str] = None) -> Tuple[str, Optional[int]]:
    """
    Convenience wrapper: generate text with the configured provider.
    """
    return get_llm().generate(user_text, system_prompt=system_prompt)

from .models import UserMessage, Response, Context

# samos/api/providers/__init__.py
"""
Provider re-exports for image generation (Phase 11.1).

- Image providers only (no LLM imports).
- Defensive: try new locations first, then legacy fallbacks.
"""

from __future__ import annotations

import importlib

__all__: list[str] = []


def _try(path: str, attr: str):
    try:
        mod = importlib.import_module(path)
        return getattr(mod, attr)
    except Exception:
        return None


# StubProvider ---------------------------------------------------------------
StubProvider = _try("samos.api.image.stub", "StubProvider") or _try(
    "samos.api.providers.stub", "StubProvider"
)
if StubProvider:
    __all__.append("StubProvider")

# OpenAIImages (alias to OpenAIProvider in new location) ---------------------
OpenAIImages = _try("samos.api.image.openai_provider", "OpenAIProvider") or _try(
    "samos.api.providers.openai_provider", "OpenAIImages"
)
if OpenAIImages:
    __all__.append("OpenAIImages")

# StabilityImages (optional legacy provider) ---------------------------------
StabilityImages = _try("samos.api.providers.stability_provider", "StabilityImages")
if StabilityImages:
    __all__.append("StabilityImages")

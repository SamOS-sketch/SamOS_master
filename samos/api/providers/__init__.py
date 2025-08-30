# samos/api/providers/__init__.py
"""
Provider re-exports for image generation (Phase 11.1).

- Keep image providers only.
- Be defensive: import what's available without type-ignores.
- Do NOT import LLM providers here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__: list[str] = []

# StubProvider ---------------------------------------------------------------
try:
    from samos.api.image.stub import StubProvider  # new location
except Exception:
    try:
        from .stub import StubProvider  # legacy fallback
    except Exception:  # pragma: no cover
        StubProvider = None  # type: ignore[assignment]

if StubProvider is not None:  # type: ignore[comparison-overlap]
    __all__.append("StubProvider")

# OpenAIImages (alias to OpenAIProvider) -------------------------------------
OpenAIImages = None
try:
    # new provider class
    from samos.api.image.openai_provider import OpenAIProvider as _OpenAIImages

    OpenAIImages = _OpenAIImages  # keep historical symbol
except Exception:
    try:
        # legacy provider symbol if present
        from .openai_provider import OpenAIImages as _LegacyOpenAIImages

        OpenAIImages = _LegacyOpenAIImages
    except Exception:  # pragma: no cover
        OpenAIImages = None

if OpenAIImages is not None:
    __all__.append("OpenAIImages")

# StabilityImages (optional) -------------------------------------------------
try:
    from .stability_provider import StabilityImages  # optional
except Exception:  # pragma: no cover
    StabilityImages = None  # type: ignore[assignment]

if StabilityImages is not None:  # type: ignore[comparison-overlap]
    __all__.append("StabilityImages")

# Nothing LLM-related is re-exported here on purpose.

# samos/api/providers/__init__.py
"""
Provider re-exports for image generation.

This module is defensive: it imports whichever providers are available in the
current tree and exposes a stable set of names for the rest of the codebase.

- Prefer the newer modules under `samos.api.image.*`
- Fall back to legacy locations under `samos.api.providers.*` if present
- LLM providers are intentionally NOT imported in Phase 11.1
"""

from __future__ import annotations

__all__: list[str] = []

# --- StubProvider -------------------------------------------------------------

try:
    # New location
    from samos.api.image.stub import StubProvider as _StubProvider  # type: ignore
except Exception:
    try:
        # Legacy location (if still present)
        from .stub import StubProvider as _StubProvider  # type: ignore
    except Exception:  # pragma: no cover
        _StubProvider = None  # type: ignore[assignment]

if _StubProvider is not None:
    StubProvider = _StubProvider  # type: ignore[misc,assignment]
    __all__.append("StubProvider")


# --- OpenAIImages (alias to OpenAIProvider) ----------------------------------

try:
    # New location + class name
    from samos.api.image.openai_provider import OpenAIProvider as _OpenAIImages  # type: ignore
except Exception:
    try:
        # Legacy location/class (if present)
        from .openai_provider import OpenAIImages as _OpenAIImages  # type: ignore
    except Exception:  # pragma: no cover
        _OpenAIImages = None  # type: ignore[assignment]

if _OpenAIImages is not None:
    # Keep the historical symbol name expected by routes
    OpenAIImages = _OpenAIImages  # type: ignore[misc,assignment]
    __all__.append("OpenAIImages")


# --- StabilityImages (optional provider) -------------------------------------

try:
    from .stability_provider import StabilityImages as _StabilityImages  # type: ignore
except Exception:  # pragma: no cover
    _StabilityImages = None  # type: ignore[assignment]

if _StabilityImages is not None:
    StabilityImages = _StabilityImages  # type: ignore[misc,assignment]
    __all__.append("StabilityImages")

# NOTE:
# We intentionally do not import or expose any LLM providers here (e.g., ClaudeLLM,
# OpenAILLM). Phase 11.1 focuses on image providers only, and dangling imports to
# non-existent llm modules were breaking imports at app startup.

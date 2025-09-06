# Lightweight package init; avoid heavy imports.
from .core.soulprint import load_soulprint  # re-export for convenience

__all__ = ["load_soulprint"]

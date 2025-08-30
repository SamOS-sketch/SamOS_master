# samos/api/router.py
"""
Central router shim for SamOS.

This module intentionally stays minimal to avoid circular imports:
- `routes_images.py` imports `SamRouter` from here and registers its routes onto it.
- We DO NOT import any providers or sub-routers here.

Phase 11.1: image-only; no LLM provider imports.
"""

from __future__ import annotations

from fastapi import APIRouter

# A single shared router object that other modules (e.g., routes_images.py)
# will import and register endpoints onto.
SamRouter = APIRouter()

__all__ = ["SamRouter"]

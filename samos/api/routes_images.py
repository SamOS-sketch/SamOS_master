# samos/api/routes_images.py
"""
Image routes shim (Phase 11.1)

We used to define image endpoints here, but /image/generate and session
mode handling now live in `samos.api.main`. To avoid duplicate routes
and circular imports, this module intentionally exports an empty
APIRouter that can be extended later if needed.
"""

from __future__ import annotations

from fastapi import APIRouter

# Minimal router; main.py includes this safely.
router = APIRouter()

__all__ = ["router"]

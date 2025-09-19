# samos/api/services/image_store.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from samos.api.db import Image as DBImage


OUTPUT_DIR = Path("outputs")


def resolve_file_path(image_row: DBImage) -> Optional[Path]:
    """
    Given an image row from the DB, return the expected local file path if present.
    Currently assumes outputs/<id>.png naming for stub/demo providers.
    """
    if not image_row:
        return None

    # Example: outputs/123.png
    candidate = OUTPUT_DIR / f"{image_row.id}.png"
    return candidate if candidate.exists() else None

# --- DEV helper: write a local PNG for an image id ---------------------------
from pathlib import Path
import os
import base64

from samos.config import settings

# 1×1 transparent PNG (base64) – tiny placeholder
_DEV_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMA"
    "ASsJTYQAAAAASUVORK5CYII="
)

def outputs_dir() -> Path:
    """Return the outputs directory (Phase A9/A10 convention)."""
    try:
        root = Path(getattr(settings, "SAM_STORAGE_DIR", "storage")).resolve()
    except Exception:
        root = Path("storage").resolve()
    d = root / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d

def write_dev_png(image_id: str, *, png_bytes: bytes | None = None) -> str:
    """
    DEV-ONLY convenience: write a small PNG to outputs/<image_id>.png.
    Returns the absolute file path (string). Never raises.
    Guard it with env SAMOS_WRITE_LOCAL_OUTPUTS=1.
    """
    try:
        data = png_bytes or base64.b64decode(_DEV_PNG_B64)
        dest = outputs_dir() / f"{image_id}.png"
        if not dest.exists():
            dest.write_bytes(data)
        return str(dest)
    except Exception:
        # Never break providers in dev
        return ""

# samos/api/paths.py
"""
V1 path helpers (minimal)
- Single storage root, controlled by SAM_STORAGE_DIR (default: outputs/)
- Ensure storage exists on startup
- Convert absolute<->relative paths under the storage root
"""

from __future__ import annotations

import os
from pathlib import Path

# Canonical storage root for image files
STORAGE_DIR_ENV = "SAM_STORAGE_DIR"
DEFAULT_STORAGE_DIR = "outputs"

def storage_root() -> Path:
    root = os.getenv(STORAGE_DIR_ENV, DEFAULT_STORAGE_DIR).strip() or DEFAULT_STORAGE_DIR
    p = Path(root).expanduser().resolve()
    return p

def ensure_static_dirs() -> Path:
    """
    Ensure the storage root exists (mkdir -p). Return absolute Path.
    """
    root = storage_root()
    root.mkdir(parents=True, exist_ok=True)
    return root

def to_relpath(p: Path | str) -> str:
    """
    Convert an absolute path under the storage root to a POSIX-style relative path.
    If the path is already relative, normalize to POSIX.
    If the path is absolute but not under storage, return the original as POSIX.
    """
    pp = Path(p)
    if not pp.is_absolute():
        return pp.as_posix()

    root = storage_root()
    try:
        rel = pp.resolve().relative_to(root)
        return rel.as_posix()
    except Exception:
        # Not under storage root -> keep absolute POSIX (serving code handles it)
        return pp.as_posix()

def resolve_relpath(rel: str | Path) -> Path:
    """
    Resolve a relative path into an absolute path within the storage root.
    If rel is absolute, return it unchanged.
    """
    rp = Path(rel)
    if rp.is_absolute():
        return rp
    return storage_root() / rp

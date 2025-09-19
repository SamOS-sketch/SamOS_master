# samos/api/paths.py
from __future__ import annotations
import os
from pathlib import Path

# ---- Public API -------------------------------------------------------------

def get_static_dir() -> Path:
    """
    Resolve the STATIC_DIR from environment (default ./var/static) to an absolute Path.
    Always expands ~ and normalizes separators. Does not create folders.
    """
    env_value = os.getenv("STATIC_DIR", "./var/static")
    base = Path(env_value).expanduser()
    try:
        return base.resolve()
    except Exception:
        # On some platforms resolve() can fail for non-existent paths; return as-is.
        return base


def ensure_static_dirs() -> Path:
    """
    Ensure the base static directory and required subfolders exist:
      - images/
      - tmp/refs/
      - tmp/work/
    Returns the absolute base path.
    """
    base = get_static_dir()
    (base / "images").mkdir(parents=True, exist_ok=True)
    (base / "tmp" / "refs").mkdir(parents=True, exist_ok=True)
    (base / "tmp" / "work").mkdir(parents=True, exist_ok=True)
    return base


def to_relpath(abs_path: str | Path) -> str:
    """
    Convert an absolute path under STATIC_DIR to a POSIX-style relative path for DB storage.
    Example: 'C:\\proj\\var\\static\\images\\a.png' -> 'images/a.png'
    """
    base = get_static_dir()
    abs_p = Path(abs_path).expanduser().resolve()
    try:
        rel = abs_p.relative_to(base)
    except ValueError as e:
        raise ValueError(f"Path is outside STATIC_DIR: {abs_p} (base={base})") from e
    return rel.as_posix()


def resolve_relpath(rel_path: str) -> Path:
    """
    Resolve a DB-stored relative path (POSIX style) back to an absolute path under STATIC_DIR.
    Rejects absolute inputs and prevents path traversal outside STATIC_DIR.
    """
    if not rel_path or Path(rel_path).is_absolute():
        raise ValueError(f"Expected relative path, got: {rel_path!r}")

    base = get_static_dir()
    combined = (base / Path(rel_path)).resolve()

    # Prevent traversal outside STATIC_DIR
    if combined == base or base not in combined.parents:
        # combined must be a descendant of base (not equal)
        raise ValueError(f"Resolved path escapes STATIC_DIR: {combined} (base={base})")

    return combined

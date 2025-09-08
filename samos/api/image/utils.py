# samos/api/image/utils.py
from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Optional, Union

# SSD-aware base path
from samos.core.config import STORAGE_DIR
from samos.runtime.event_logger import log_event

# Where all image files must go
OUTPUTS_PATH: Path = STORAGE_DIR / "outputs"
OUTPUTS_PATH.mkdir(parents=True, exist_ok=True)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _new_filename(ext: str = ".png") -> Path:
    if not ext.startswith("."):
        ext = "." + ext
    return OUTPUTS_PATH / f"img_{_timestamp()}{ext}"


def save_bytes(data: bytes, ext: str = ".png") -> Path:
    """
    New canonical saver: writes bytes to SSD outputs and returns the Path.
    """
    out_path = _new_filename(ext)
    out_path.write_bytes(data)
    log_event(
        "image_saved",
        {"path": str(out_path), "storage.path": str(OUTPUTS_PATH), "source": "api.utils"},
    )
    return out_path


# Back-compat helper:
# If older code tries to call save(path, data) or save_image_bytes(path, data),
# we ignore the provided 'path' and still write to the SSD outputs dir.
PathLike = Union[str, Path]


def save(path: PathLike, data: bytes, ext: Optional[str] = None) -> Path:
    suffix = ext or (Path(path).suffix if isinstance(path, (Path, str)) else ".png") or ".png"
    return save_bytes(data, suffix)


def save_image_bytes(path: PathLike, data: bytes, ext: Optional[str] = None) -> Path:
    return save(path, data, ext)


__all__ = ["OUTPUTS_PATH", "save_bytes", "save", "save_image_bytes"]

# samos/core/soulprint_loader.py
import os
from typing import Tuple, Optional
import yaml

from .persona import get_persona, Persona

# places we'll look for the file name we choose
CANDIDATES = [
    "{name}",                       # repo root
    "samos/{name}",
    "samos/resources/{name}",
    "resources/{name}",
]

def _pick_filename() -> str:
    # explicit override wins
    explicit = os.getenv("SAMOS_SOULPRINT")
    if explicit and explicit.strip():
        return explicit.strip()

    # persona default
    return "soulprint.demo.yaml" if get_persona() == Persona.DEMO else "soulprint.private.yaml"

def _resolve_path(filename: str) -> Optional[str]:
    if os.path.isabs(filename) and os.path.exists(filename):
        return filename
    if os.path.exists(filename):
        return filename
    for tpl in CANDIDATES:
        p = tpl.format(name=filename)
        if os.path.exists(p):
            return p
    return None

def load_soulprint() -> Tuple[dict, str]:
    """
    Returns (data, resolved_path).
    Resolution order:
      1) SAMOS_SOULPRINT (explicit path)
      2) persona default: private/demo filename
      3) search common folders
    """
    filename = _pick_filename()
    resolved = _resolve_path(filename)
    if not resolved:
        raise FileNotFoundError(
            f"Soulprint not found. Tried '{filename}' in {CANDIDATES}. "
            f"Set SAMOS_SOULPRINT to an explicit path if needed."
        )
    with open(resolved, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data, resolved

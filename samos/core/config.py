import os
from pathlib import Path

# NEW: load .env so SAM_STORAGE_DIR is available when running locally
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(".env"))
except Exception:
    # ok if python-dotenv isn't installed; env var may be set by shell
    pass

def get_storage_dir() -> Path:

    """
    Resolve SamOS storage directory.
    Priority:
    1. SAM_STORAGE_DIR env var (from .env or system)
    2. Default to ./.samos
    """
    # Look for env var
    base = os.getenv("SAM_STORAGE_DIR")

    if base:
        storage_path = Path(base)
    else:
        storage_path = Path(".samos")

    # Ensure subdirectories exist
    for sub in ["memory", "events", "outputs", "cache"]:
        (storage_path / sub).mkdir(parents=True, exist_ok=True)

    return storage_path

# Global singleton path (optional)
STORAGE_DIR = get_storage_dir()

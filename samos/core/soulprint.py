from pathlib import Path
import yaml

# soulprint.yaml lives at repo root
DEFAULT_SOULPRINT_PATH = Path(__file__).resolve().parents[2] / "soulprint.yaml"

def load_soulprint(path: str | Path | None = None) -> dict:
    p = Path(path) if path else DEFAULT_SOULPRINT_PATH
    if not p.exists():
        # Return empty dict rather than crash; tests can assert on this if needed.
        return {}
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}

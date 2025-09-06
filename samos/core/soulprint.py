from pathlib import Path
import yaml

# soulprint.yaml lives at repo root
DEFAULT_SOULPRINT_PATH = Path(__file__).resolve().parents[2] / "soulprint.yaml"


# ---- Back-compat class expected by older tests/code --------------------------
class Soulprint(dict):
    """
    Dict-like wrapper around the soulprint data with legacy helpers.
    """

    # tests call: Soulprint.load(path)
    @classmethod
    def load(cls, path: str | Path | None = None, strict: bool = True) -> "Soulprint":
        p = Path(path) if path else DEFAULT_SOULPRINT_PATH
        if not p.exists():
            if strict:
                raise ValueError(f"soulprint file not found: {p}")
            return cls({})

        try:
            with p.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            if strict:
                raise ValueError(f"invalid soulprint yaml: {e}") from e
            return cls({})

        # Normalize & basic validation
        if data is None or not isinstance(data, dict):
            if strict:
                raise ValueError("soulprint must be a mapping (YAML dict)")
            data = {}

        # Minimal schema check for strict mode expected by tests
        if strict:
            ident = data.get("identity")
            if not isinstance(ident, dict) or not ident.get("name"):
                raise ValueError("invalid soulprint: missing identity.name")

        return cls(data)

    # property some tests expect
    @property
    def identity(self) -> dict:
        return self.get("identity", {})

    # helper some skills/tests call → must return "Name | tone | s"
    def voice_tag(self) -> str:
        name = (self.identity.get("name") or self.get("name") or "Sam")
        tone = (self.identity.get("tone") or self.get("tone") or "warm")
        return f"{name} | {tone} | s"
# ----------------------------------------------------------------------------


def load_soulprint(path: str | Path | None = None) -> dict:
    """Non-strict loader used by runtime: missing/invalid -> {}."""
    try:
        return dict(Soulprint.load(path, strict=False))
    except Exception:
        return {}


def load_soulprint_obj(path: str | Path | None = None) -> Soulprint:
    """Return a Soulprint object (non-strict for runtime)."""
    try:
        return Soulprint.load(path, strict=False)
    except Exception:
        return Soulprint({})

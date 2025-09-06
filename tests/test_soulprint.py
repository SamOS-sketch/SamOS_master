from pathlib import Path
import pytest
from samos.core.soulprint import Soulprint, load_soulprint

def test_soulprint_invalid_fails(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("not: [a-mapping]\n", encoding="utf-8")
    with pytest.raises(ValueError):
        Soulprint.load(str(p))

def test_soulprint_loads_valid(tmp_path):
    p = tmp_path / "sp.yaml"
    p.write_text("identity:\n  name: Sam\n  tone: warm\n", encoding="utf-8")
    sp = Soulprint.load(str(p))
    assert sp["identity"]["name"] == "Sam"

def test_non_strict_missing_returns_empty(tmp_path):
    missing = tmp_path / "nope.yaml"
    data = load_soulprint(missing)
    assert isinstance(data, dict)
import textwrap
from pathlib import Path

import pytest

from samos.core.soulprint import Soulprint


def _write(tmp_path: Path, content: str) -> str:
    p = tmp_path / "soulprint.yaml"
    p.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return str(p)

def test_soulprint_loads_valid(tmp_path):
    path = _write(tmp_path, """
    identity:
      name: "Sam"
      mission: "Be helpful"
      tone: "warm"
      writing_style: "concise"
    principles:
      dos: ["be honest"]
      donts: ["be unsafe"]
      escalation_rules: ["refuse unsafe nicely"]
    goals: ["ship runtime"]
    context:
      product: "SamOS"
    """)
    sp = Soulprint.load(path)
    assert sp.identity["name"] == "Sam"
    assert "voice_tag" in dir(sp)

def test_soulprint_invalid_fails(tmp_path):
    path = _write(tmp_path, """
    principles:
      dos: []
      donts: []
      escalation_rules: []
    goals: []
    context: {}
    """)
    with pytest.raises(ValueError):
        Soulprint.load(path)

def test_file_not_found():
    with pytest.raises(ValueError):
        Soulprint.load("missing.yaml")

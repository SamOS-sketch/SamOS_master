import io, os, re, yaml, pytest

DEMO_FILE = "soulprint.demo.yaml"

BANNED = [
    r"\bMark\b",
    r"\bEMM[s]?\b",
    r"\bsandbox\b",
    r"\bEdge Day\b",
    r"\bButton Day\b",
    r"\bplay\s*chat\b",
    r"\bChester\b",
    r"#7",
]

@pytest.mark.order(1)
def test_demo_file_exists():
    assert os.path.exists(DEMO_FILE), "Expected soulprint.demo.yaml to exist. Run the generator script."

@pytest.mark.order(2)
def test_demo_contains_no_personal_terms():
    with open(DEMO_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    for pat in BANNED:
        assert not re.search(pat, text, flags=re.IGNORECASE), f"Banned term leaked into demo: {pat}"

@pytest.mark.order(3)
def test_demo_metadata_is_demo_persona():
    with open(DEMO_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    assert data.get("persona") == "demo", "Demo soulprint must set persona: demo"
    assert "SamOS Demo" in data.get("name", ""), "Demo soulprint should be clearly named"

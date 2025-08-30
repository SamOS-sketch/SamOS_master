import os
import importlib
import sys
from fastapi.testclient import TestClient

os.environ["SAMOS_PERSONA"] = "demo"
os.environ.pop("SOULPRINT_PATH", None)

# ensure modules re-read env
if "samos.config" in sys.modules:
    importlib.reload(sys.modules["samos.config"])
if "samos.api.main" in sys.modules:
    importlib.reload(sys.modules["samos.api.main"])

from samos.api.main import app  # noqa: E402

client = TestClient(app)

def test_health_reports_demo_soulprint():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    sp = str(data.get("soulprint_path", ""))
    # Accept either the actual demo file or UNAVAILABLE (when not present in test env)
    assert (sp.endswith("soulprint.demo.yaml")) or (sp.upper() == "UNAVAILABLE")
    assert isinstance(data.get("provider"), str)

def test_session_and_image_happy_path():
    r = client.post("/session/start")
    assert r.status_code == 200
    sid = r.json()["session_id"]

    r = client.post("/image/generate", json={"session_id": sid, "prompt": "hello world"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "ok"
    assert isinstance(data.get("provider"), str)
    assert "image_id" in data

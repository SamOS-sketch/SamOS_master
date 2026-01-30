# tests/test_health.py
from fastapi.testclient import TestClient

from samos.api.main import app


def test_health_endpoint_alive():
    """
    Health must be:
    - reachable
    - dependency-free
    - stable
    """
    client = TestClient(app)
    r = client.get("/health")

    assert r.status_code == 200
    payload = r.json()
    assert payload == {"ok": True, "status": "alive"}

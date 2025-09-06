import pytest
import requests
from samos.providers.openai_client import OpenAIClient, OpenAIConfig

class DummyResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {"choices": [{"message": {"content": "hi"}}]}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

def test_env_missing_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as e:
        OpenAIConfig()
    assert "missing" in str(e.value).lower()

def test_success_path(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cfg = OpenAIConfig()
    client = OpenAIClient(cfg)

    def fake_post(url, headers, json, timeout):
        return DummyResp(200)

    client._session.post = fake_post  # type: ignore
    out = client.chat([{"role": "user", "content": "Hello"}])
    assert out["ok"] is True
    assert out["text"] == "hi"
    assert "latency_ms" in out

def test_network_error_returns_ok_false(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cfg = OpenAIConfig()
    client = OpenAIClient(cfg)

    def fake_post(url, headers, json, timeout):
        raise requests.exceptions.RequestException("boom")

    client._session.post = fake_post  # type: ignore
    out = client.chat([{"role": "user", "content": "Hello"}])
    assert out["ok"] is False
    assert "error" in out

def test_429_retries_then_success(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cfg = OpenAIConfig()
    client = OpenAIClient(cfg)

    calls = {"n": 0}
    def fake_post(url, headers, json, timeout):
        calls["n"] += 1
        if calls["n"] < 3:
            return DummyResp(429, {"error": {"message": "rate limit"}})
        return DummyResp(200)

    client._session.post = fake_post  # type: ignore
    out = client.chat([{"role": "user", "content": "Hello"}])
    assert out["ok"] is True
    assert calls["n"] == 3

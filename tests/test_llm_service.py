import pytest
from samos.providers.llm_service import LLMService

def test_service_success(monkeypatch):
    # Patch OpenAIClient + OpenAIConfig inside the module so we avoid real env/network
    import samos.providers.llm_service as llm_mod

    class FakeConfig:
        pass

    class FakeOpenAIClient:
        def __init__(self, cfg): pass
        def chat(self, msgs):
            return {"ok": True, "text": "hello", "latency_ms": 12}

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_mod, "OpenAIClient", FakeOpenAIClient)
    monkeypatch.setattr(llm_mod, "OpenAIConfig", lambda: FakeConfig())

    svc = LLMService(provider="openai")
    text, latency = svc.generate("hey", system_prompt="sys")
    assert text == "hello"
    assert latency == 12

def test_service_failure_raises(monkeypatch):
    import samos.providers.llm_service as llm_mod

    class FakeConfig:
        pass

    class FakeOpenAIClient:
        def __init__(self, cfg): pass
        def chat(self, msgs):
            return {"ok": False, "error": "bad"}

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_mod, "OpenAIClient", FakeOpenAIClient)
    monkeypatch.setattr(llm_mod, "OpenAIConfig", lambda: FakeConfig())

    svc = LLMService(provider="openai")
    with pytest.raises(RuntimeError) as e:
        svc.generate("x")
    assert "llm.fail" in str(e.value)

def test_service_stub_mode():
    svc = LLMService(provider="local")
    text, latency = svc.generate("ping")
    assert text == "[stub] ping"
    assert latency is None

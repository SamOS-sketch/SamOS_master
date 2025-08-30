import importlib

import pytest


def test_demo_cannot_point_to_private_soulprint(monkeypatch):
    # Set env to trip the validator
    monkeypatch.setenv("SAMOS_PERSONA", "demo")
    monkeypatch.setenv("SOULPRINT_PATH", "soulprint.private.yaml")

    # Reload the config module so BaseSettings re-reads env
    with pytest.raises(Exception):
        cfg = importlib.import_module("samos.config")
        importlib.reload(cfg)

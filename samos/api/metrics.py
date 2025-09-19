# samos/api/metrics.py
from __future__ import annotations

import threading
from typing import Dict

# Thread-safe in-process metrics store
_LOCK = threading.Lock()
_METRICS: Dict[str, int] = {}

def _inc(key: str, n: int = 1) -> None:
    if not key:
        return
    with _LOCK:
        _METRICS[key] = _METRICS.get(key, 0) + int(n)

# Public helpers we’ll call from routes
def inc_ok(provider: str) -> None:
    _inc(f"image.ok.{(provider or '').strip().lower()}")

def inc_fail(provider: str) -> None:
    _inc(f"image.fail.{(provider or '').strip().lower()}")

def inc(key: str, n: int = 1) -> None:
    """Generic counter (e.g., 'image.ref.used', 'image.drift.detected')."""
    _inc(key, n)

def snapshot() -> Dict[str, int]:
    """Return a copy of all counters."""
    with _LOCK:
        return dict(_METRICS)

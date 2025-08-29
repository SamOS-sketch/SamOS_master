# samos/core/memory_agent.py
from __future__ import annotations
from typing import Optional, Dict, Any
from .persona import get_persona, Persona

class MemoryAgent:
    """
    Persona-aware memory hooks.
    - private: accepts themes/insights/EMMs/events
    - demo:    accepts only neutral insights/events; drops personal/EMM
    """

    def __init__(self, persona: Optional[Persona] = None):
        self.persona = persona or get_persona()
        self._demo_ban = ("mark", "emm", "sandbox", "edge day", "button day", "chester")

    def _demo_safe(self, text: str) -> bool:
        t = (text or "").lower()
        return not any(b in t for b in self._demo_ban)

    # ---- Hooks (no-ops for now; split behavior enforced) ----
    def on_session_start(self, session_id: str, mode: str) -> None:
        pass

    def on_event(self, session_id: Optional[str], kind: str, message: str, meta: Dict[str, Any]) -> None:
        # demo allowed; keep generic
        pass

    def on_insight(self, session_id: str, key: str, value: str) -> None:
        if self.persona == Persona.DEMO:
            if not (self._demo_safe(key) and self._demo_safe(value)):
                return  # drop in demo
        # private would summarize/persist here in future
        pass

    def on_emm(self, session_id: str, emm_type: str, message: str) -> None:
        if self.persona == Persona.DEMO:
            return  # never learn EMMs in demo
        # private would process here
        pass

_AGENT: Optional[MemoryAgent] = None
def get_memory_agent() -> MemoryAgent:
    global _AGENT
    if _AGENT is None:
        _AGENT = MemoryAgent()
    return _AGENT

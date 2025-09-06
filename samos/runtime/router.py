from __future__ import annotations
from typing import List, Optional, Dict, Any
from samos.runtime.models import UserMessage, Response, Context
from samos.skills.base import Skill
from samos.memory.store import MemoryStore
from samos.runtime.memory_agent import MemoryAgent

def _voice_tag(soul: Any) -> str:
    vt = getattr(soul, "voice_tag", None)
    if callable(vt):
        try:
            return vt() or "Sam"
        except Exception:
            pass
    if isinstance(soul, dict):
        v = soul.get("voice_tag") or soul.get("name")
        if isinstance(v, str) and v.strip():
            return v.strip()
    return "Sam"

class Router:
    def __init__(self, skills: List[Skill], memory_store: Optional[MemoryStore] = None):
        if not skills:
            raise ValueError("Router requires at least one skill")
        self.skills = skills
        self.memory = memory_store or MemoryStore()
        self.agent = MemoryAgent(self.memory)

    def handle(self, msg: UserMessage, ctx: Context) -> Response:
        # 1) Pre-hook: user-initiated notes ("Remember:" / "Note:")
        saved = self._maybe_store_user_note(msg, ctx)
        if saved:
            return Response(text=f"{_voice_tag(ctx.soulprint)}: Saved that to memory.")

        # 2) Route to first supporting skill
        for skill in self.skills:
            try:
                if skill.supports(msg, ctx):
                    resp = skill.run(msg, ctx)
                    # 3) Post-hook: skills can ask to remember via resp.meta["remember"]
                    self._maybe_store_from_response(resp)
                    # 4) MemoryAgent: auto-learn themes, insights, EMMs, events
                    self.agent.process(msg, resp, ctx)
                    return resp
            except Exception as e:
                return Response(text=f"{_voice_tag(ctx.soulprint)}: error in {skill.name} - {e}")

        return Response(text=f"{_voice_tag(ctx.soulprint)}: no skill could handle the request.")

    # ---------- hooks ----------
    def _maybe_store_user_note(self, msg: UserMessage, ctx: Context) -> bool:
        t = msg.text.strip()
        lower = t.lower()
        if lower.startswith("remember:") or lower.startswith("note:"):
            content = t.split(":", 1)[1].strip()
            if content:
                self.memory.add_memory(content, tags=["user", "note"], importance=4)
                return True
        return False

    def _maybe_store_from_response(self, resp: Response) -> None:
        payload: Optional[Dict[str, Any]] = resp.meta.get("remember") if resp and resp.meta else None
        if not payload:
            return
        text = str(payload.get("text", "")).strip()
        if not text:
            return
        tags = payload.get("tags") or ["auto"]
        importance = int(payload.get("importance", 3))
        importance = 1 if importance < 1 else 5 if importance > 5 else importance
        self.memory.add_memory(text, tags=tags, importance=importance)

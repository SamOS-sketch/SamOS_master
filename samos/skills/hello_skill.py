from __future__ import annotations
from typing import Optional
from samos.runtime.models import UserMessage, Response, Context
from samos.skills.base import Skill
from samos.runtime import llm_generate

class HelloSkill(Skill):
    name = "hello"

    # Keep simple for now: allow this skill to handle general text
    def supports(self, msg: UserMessage, ctx: Context) -> bool:
        return True

    def run(self, msg: UserMessage, ctx: Context) -> Response:
        # Try to pull a system/tone prompt from the soulprint if available
        system_prompt: Optional[str] = None
        sp = getattr(ctx, "soulprint", None)
        if sp:
            for attr in ("system_prompt", "prompt", "tone_prompt"):
                fn = getattr(sp, attr, None)
                if callable(fn):
                    try:
                        system_prompt = fn()
                        break
                    except Exception:
                        pass

        text, latency_ms = llm_generate(msg.text, system_prompt=system_prompt)
        return Response(text=text, meta={"latency_ms": latency_ms})

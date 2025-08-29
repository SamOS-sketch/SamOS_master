from __future__ import annotations
import re
from samos.runtime.models import UserMessage, Response, Context

class SummarizeSkill:
    name = "summarize"

    def supports(self, msg: UserMessage, ctx: Context) -> bool:
        return msg.text.strip().lower().startswith("summarize:")

    def run(self, msg: UserMessage, ctx: Context) -> Response:
        text = msg.text.split(":", 1)[1].strip()
        if not text:
            return Response(text=f"{ctx.soulprint.voice_tag()}: (nothing to summarize)")
        summary = _naive_summary(text)
        return Response(text=f"{ctx.soulprint.voice_tag()}: {summary}")

def _naive_summary(s: str, max_sentences: int = 3) -> str:
    # very lightweight: keep first N “sentences”, fallback to chunking
    parts = re.split(r'(?<=[.!?])\s+', s.strip())
    if len(parts) <= max_sentences:
        return s.strip()
    out = " ".join(parts[:max_sentences]).strip()
    if not out.endswith((".", "!", "?")):
        out += "…"
    return out

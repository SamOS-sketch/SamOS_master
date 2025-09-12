# samos/skills/summarize_skill.py

import os, re, time
from dataclasses import dataclass
from typing import Dict, Any

from samos.runtime.models import UserMessage, Context, Response

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore


@dataclass
class SummarizeSkill:
    name: str = "SummarizeSkill"

    # Router API
    def supports(self, msg: UserMessage, ctx: Context) -> bool:
        t = (msg.text or "").strip().lower()
        return t.startswith("summarize:") or t.startswith("summarise:") or t.startswith("tl;dr:")

    def run(self, msg: UserMessage, ctx: Context) -> Response:
        if hasattr(ctx, "events"):
            with ctx.events.span("skill", skill=self.name):  # type: ignore[attr-defined]
                return self._execute(msg, ctx)
        return self._execute(msg, ctx)

    # Core logic
    def _execute(self, msg: UserMessage, ctx: Context) -> Response:
        raw = (msg.text or "").strip()
        body = re.sub(r"^(summari[sz]e:|tl;dr:)\s*", "", raw, flags=re.IGNORECASE).strip()

        provider = getattr(ctx, "provider", None) or os.getenv("SAM_PROVIDER", "openai")
        provider = str(provider).lower()

        if provider in {"echo", "stub"}:
            return Response(
                text=self._local_summary(body),
                meta={"provider": provider, "skill": self.name, "mode": "local"},
            )

        if provider == "openai" and OpenAI is not None:
            return self._openai_summary(body, ctx)

        return Response(
            text=self._local_summary(body),
            meta={"provider": provider, "skill": self.name, "fallback": "sdk_unavailable_or_unknown_provider"},
        )

    # OpenAI path with event logging
    def _openai_summary(self, body: str, ctx: Context) -> Response:
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2") or 0.2)
        max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "300") or 300)

        system_prompt = (
            "You are a precise and concise summarizer. "
            "Return a clear summary of the user's text in 1–3 short bullet points or 2–4 short sentences. "
            "Keep it under ~80 words. Preserve key facts and numbers. Avoid hype."
        )
        prompt = f"{system_prompt}\n\n=== TEXT ===\n{body}\n\n=== TASK ===\nProvide the summary now."

        client = OpenAI(api_key=api_key, base_url=base_url)  # type: ignore

        if hasattr(ctx, "events"):
            with ctx.events.span("llm", provider="openai", model=model, skill=self.name, input_chars=len(prompt)):  # type: ignore[attr-defined]
                resp = client.responses.create(  # type: ignore[attr-defined]
                    model=model,
                    input=prompt,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
        else:
            resp = client.responses.create(  # type: ignore[attr-defined]
                model=model,
                input=prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

        summary_text = getattr(resp, "output_text", None)
        if not summary_text:
            try:
                parts = []
                for item in getattr(resp, "output", []) or []:
                    if getattr(item, "type", "") == "message":
                        for c in getattr(item, "content", []) or []:
                            if getattr(c, "type", "") == "output_text":
                                parts.append(getattr(c, "text", ""))
                summary_text = " ".join(parts).strip()
            except Exception:
                summary_text = ""

        if not summary_text:
            summary_text = "[local-summary] " + self._truncate(body)

        return Response(
            text=summary_text.strip(),
            meta={"provider": "openai", "skill": self.name, "model": model},
        )

    # Local fallback
    def _local_summary(self, text: str, hard_limit: int = 80) -> str:
        parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
        snippet = " ".join(parts[:2]).strip() or (text or "").strip()
        words = snippet.split()
        if len(words) > hard_limit:
            snippet = " ".join(words[:hard_limit]) + "…"
        return f"[local-summary] {snippet}"

    def _truncate(self, text: str, hard_limit: int = 80) -> str:
        words = (text or "").split()
        return " ".join(words[:hard_limit]) + ("…" if len(words) > hard_limit else "")

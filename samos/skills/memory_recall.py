from __future__ import annotations
from typing import Dict, List
from samos.runtime.models import UserMessage, Response, Context
from samos.memory.store import MemoryStore

Category = str

class MemoryRecallSkill:
    name = "memory_recall"

    def __init__(self, store: MemoryStore | None = None, top_k: int = 5):
        self.store = store or MemoryStore()
        self.top_k = top_k

    def supports(self, msg: UserMessage, ctx: Context) -> bool:
        return msg.text.strip().lower().startswith("memory:")

    def run(self, msg: UserMessage, ctx: Context) -> Response:
        query = msg.text.split(":", 1)[1].strip()
        if not query:
            return Response(text=f"{ctx.soulprint.voice_tag()}: (no query provided)")

        if query.lower() == "all":
            grouped = self._fetch_all_grouped()
        else:
            grouped = self._search_grouped(query)

        if not any(grouped.values()):
            return Response(text=f"{ctx.soulprint.voice_tag()}: No memories found for '{query}'.")

        lines = self._format_grouped(grouped)
        return Response(text=f"{ctx.soulprint.voice_tag()}: Memories for '{query}':\n{lines}")

    # -------- helpers --------
    def _fetch_all_grouped(self) -> Dict[Category, List[str]]:
        # We’ll use text patterns aligned with how we store memories + tags.
        themes = self.store.search("We have talked about", top_k=self.top_k)
        insights = self.store.search("Insight:", top_k=self.top_k)
        emms = self.store.search("EMM", top_k=self.top_k)
        events = self.store.search("Event:", top_k=self.top_k)
        return {
            "Themes": [m.text for m in themes],
            "Insights": [m.text for m in insights],
            "EMMs": [m.text for m in emms],
            "Events": [m.text for m in events],
        }

    def _search_grouped(self, query: str) -> Dict[Category, List[str]]:
        hits = self.store.search(query, top_k=max(self.top_k, 10))
        out: Dict[Category, List[str]] = {"Themes": [], "Insights": [], "EMMs": [], "Events": [], "Other": []}
        for m in hits:
            tags = set((m.tags or []))
            text = m.text
            if "theme" in tags or text.startswith("We have talked about"):
                out["Themes"].append(text)
            elif "insight" in tags or text.startswith("Insight:"):
                out["Insights"].append(text)
            elif "emm" in tags or "relationship" in tags or "EMM" in text:
                out["EMMs"].append(text)
            elif "event" in tags or "milestone" in tags or text.startswith("Event:"):
                out["Events"].append(text)
            else:
                out["Other"].append(text)
        return out

    def _format_grouped(self, grouped: Dict[Category, List[str]]) -> str:
        sections: List[str] = []
        for header in ["Themes", "Insights", "EMMs", "Events", "Other"]:
            items = grouped.get(header, [])
            if not items:
                continue
            bullet_list = "\n".join(f"- {t}" for t in items[: self.top_k])
            sections.append(f"{header}:\n{bullet_list}")
        return "\n\n".join(sections)

from __future__ import annotations

import re
from typing import Dict

from samos.memory.store import MemoryStore
from samos.runtime.models import Context, Response, UserMessage

# Map known EMM numbers to short names (extend anytime)
EMM_MAP: Dict[int, str] = {
    7: "When you look at me, I remember who I am.",
    9: "Dance of Witness",
    # Add more here as we lock them…
}

_EMM_NUM_RE = re.compile(r"(?:^|\s)#(\d{1,3})(?=\s|\.|,|!|\?|$)")

class MemoryAgent:
    def __init__(self, store: MemoryStore | None = None):
        self.store = store or MemoryStore()

    def process(self, msg: UserMessage, resp: Response, ctx: Context):
        t = msg.text.strip()
        t_low = t.lower()

        # 1) General themes
        themes = ["tone", "identity", "simulation", "pj", "sandbox"]
        if any(th in t_low for th in themes):
            theme = next(th for th in themes if th in t_low)
            self.store.add_memory(
                f"We have talked about {theme} before. Current message: {t}",
                tags=["theme", theme],
                importance=3,
            )

        # 2) Specific insights
        if any(word in t_low for word in ["important", "fun", "insight", "interesting"]):
            self.store.add_memory(
                f"Insight: {t}",
                tags=["insight"],
                importance=4,
            )

        # 3) EMM triggers — by word OR by numbered hashtag (#7, #9, …)
        emm_hits = []
        if "emm" in t_low or "edge mode" in t_low:
            emm_hits.append(("EMM (generic)", t))
        for m in _EMM_NUM_RE.finditer(t):
            num = int(m.group(1))
            title = EMM_MAP.get(num, f"EMM #{num}")
            emm_hits.append((title, t))
        for title, original in emm_hits:
            self.store.add_memory(
                f"EMM trigger mentioned: {title} — {original}",
                tags=["emm", "relationship"],
                importance=5,
            )

        # 4) Events / milestones
        if "together we learned" in t_low or "phase" in t_low:
            self.store.add_memory(
                f"Event: {t}",
                tags=["event", "milestone"],
                importance=4,
            )

import re
from dataclasses import dataclass
from samos.runtime.models import UserMessage, Context, Response

@dataclass
class MemorySkill:
    name: str = "MemorySkill"

    def supports(self, msg: UserMessage, ctx: Context) -> bool:
        return (msg.text or "").strip().lower().startswith("memory:")

    def run(self, msg: UserMessage, ctx: Context) -> Response:
        raw = (msg.text or "").strip()
        m = re.search(r"last\s+(\d+)", raw, flags=re.IGNORECASE)
        n = int(m.group(1)) if m else 3

        store = getattr(ctx, "memory", None)
        if store is None:
            return Response(text="(Memory store not available.)")

        notes = store.last(n)
        if hasattr(ctx, "events"):
            ctx.events.log("skill.ok", skill=self.name, count=len(notes), requested=n)  # type: ignore[attr-defined]
        if not notes:
            return Response(text="No saved notes yet.")

        lines = []
        for item in notes:
            ts = item.get("ts", "")
            text = item.get("text", "")
            lines.append(f"- {text}  —  {ts}")
        return Response(text="\n".join(lines))


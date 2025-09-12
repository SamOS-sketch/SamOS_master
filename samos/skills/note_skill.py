import re
from dataclasses import dataclass
from samos.runtime.models import UserMessage, Context, Response

@dataclass
class NoteSkill:
    name: str = "NoteSkill"

    def supports(self, msg: UserMessage, ctx: Context) -> bool:
        return (msg.text or "").strip().lower().startswith("note:")

    def run(self, msg: UserMessage, ctx: Context) -> Response:
        raw = (msg.text or "").strip()
        body = re.sub(r"^note:\s*", "", raw, flags=re.IGNORECASE).strip()

        store = getattr(ctx, "memory", None)
        if store is None:
            return Response(text="(Memory store not available — note not saved.)")

        entry = store.add_note(body, meta={"skill": self.name})
        if hasattr(ctx, "events"):
            ctx.events.log("skill.ok", skill=self.name, saved_at=entry["ts"], text_len=len(body))  # type: ignore[attr-defined]
        return Response(text=f"Noted: {body}", meta={"saved_at": entry["ts"]})


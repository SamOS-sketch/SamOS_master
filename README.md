# SamOS\\nMinimal runtime for Phase 10.

\## Build a Skill in 60 seconds



Create `my\_skill.py`:

```python

from samos.runtime.models import UserMessage, Response, Context



class MySkill:

&nbsp; name = "my\_skill"

&nbsp; def supports(self, msg: UserMessage, ctx: Context) -> bool:

&nbsp;   return msg.text.strip().lower().startswith("do:")

&nbsp; def run(self, msg: UserMessage, ctx: Context) -> Response:

&nbsp;   task = msg.text.split(":",1)\[1].strip() or "(nothing)"

&nbsp;   return Response(text=f"{ctx.soulprint.voice\_tag()}: doing {task}")


## 📌 Project Milestone

**Current Stable Baseline:** `phase10-clean` (tag: `v0.1.0-phase10-clean`)

Following lessons from Phase 11+, the SamOS codebase has been reset to a clean,
stable state at Phase 10. This branch now serves as the **canonical foundation**
for all future development.

- Phase 10: Soulprint, minimal runtime, memory persistence, SDK surface, CLI.
- Phase 11+: Postmortem documented in project notes (not carried into code).
- Next: Roadmap features (Persona split, Heartbeat, Pulse) staged for v2.

**Note:** If you are cloning or contributing, please start from
`phase10-clean`. Older branches are archived for reference only.


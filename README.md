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




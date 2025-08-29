# SamOS\\nMinimal runtime for Phase 10.

\## Build a Skill in 60 seconds

# SamOS_master

![Build Status](https://img.shields.io/badge/tests-passing-brightgreen)
![Phase](https://img.shields.io/badge/phase-10%20✔-blue)
![Version](https://img.shields.io/badge/version-v0.1.0--phase10-orange)
![License](https://img.shields.io/badge/license-private-lightgrey)

---

Minimal runtime for Phase 10.  
SamOS is evolving through structured development phases, each tagged in GitHub for clarity.  



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




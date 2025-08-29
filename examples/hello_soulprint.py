from __future__ import annotations
import os
from samos.core.soulprint import Soulprint
from samos.runtime.models import Context, UserMessage
from samos.runtime.router import Router
from samos.skills.echo import EchoSkill
from examples.skills.hello_skill import HelloSkill

def run():
    sp = Soulprint.load(os.getenv("SAMOS_SOULPRINT", "soulprint.yaml"))
    ctx = Context(soulprint=sp)
    router = Router([HelloSkill(), EchoSkill()])
    resp = router.handle(UserMessage(text="hello, soulprint"), ctx)
    print(resp.text)

if __name__ == "__main__":
    run()

from __future__ import annotations
import os, sys
from samos.core.soulprint import Soulprint
from samos.runtime.models import Context, UserMessage
from samos.runtime.router import Router
from samos.skills.echo import EchoSkill
from samos.skills.memory_recall import MemoryRecallSkill
from samos.skills.summarize import SummarizeSkill

def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Usage: samos \"your prompt\"")
        return 2
    sp = Soulprint.load(os.getenv("SAMOS_SOULPRINT", "soulprint.yaml"))
    ctx = Context(soulprint=sp)
    router = Router([MemoryRecallSkill(), SummarizeSkill(), EchoSkill()])
    resp = router.handle(UserMessage(text=" ".join(argv)), ctx)
    print(resp.text)
    return 0

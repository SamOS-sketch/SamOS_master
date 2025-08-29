from __future__ import annotations
from samos.runtime.models import UserMessage, Response, Context

class EchoSkill:
    name = "echo"

    def supports(self, msg: UserMessage, ctx: Context) -> bool:
        return True  # always available

    def run(self, msg: UserMessage, ctx: Context) -> Response:
        return Response(text=f"{ctx.soulprint.voice_tag()}: {msg.text}")

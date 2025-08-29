# Minimal example of a drop-in skill
from __future__ import annotations
from samos.runtime.models import UserMessage, Response, Context

class HelloSkill:
    name = "hello"

    def supports(self, msg: UserMessage, ctx: Context) -> bool:
        return msg.text.strip().lower() == "hello, soulprint"

    def run(self, msg: UserMessage, ctx: Context) -> Response:
        ident = ctx.soulprint.identity
        return Response(text=f"{ident['name']} · {ident['tone']}: Hello back — I’m {ident['name']} and my mission is: {ident['mission']}")

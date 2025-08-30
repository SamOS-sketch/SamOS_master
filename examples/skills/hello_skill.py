# Minimal example of a drop-in skill
from __future__ import annotations

from samos.runtime.models import Context, Response, UserMessage


class HelloSkill:
    name = "hello"

    def supports(self, msg: UserMessage, ctx: Context) -> bool:
        return msg.text.strip().lower() == "hello, soulprint"

    def run(self, msg: UserMessage, ctx: Context) -> Response:
        ident = ctx.soulprint.identity
        return (
            f"Hello back — I'm {ident['name']} "
            f"and my mission is: {ident['mission']}"
        )

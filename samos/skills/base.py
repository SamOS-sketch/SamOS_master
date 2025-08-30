from __future__ import annotations

from typing import Protocol

from samos.runtime.models import Context, Response, UserMessage


class Skill(Protocol):
    name: str
    def supports(self, msg: UserMessage, ctx: Context) -> bool: ...
    def run(self, msg: UserMessage, ctx: Context) -> Response: ...

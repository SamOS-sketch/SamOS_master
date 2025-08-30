from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel, ValidationError


class _Identity(BaseModel):
    name: str
    mission: str
    tone: str
    writing_style: str

class _Principles(BaseModel):
    dos: List[str]
    donts: List[str]
    escalation_rules: List[str]

class _SoulprintModel(BaseModel):
    identity: _Identity
    principles: _Principles
    goals: List[str]
    context: Dict[str, Any]

@dataclass(frozen=True)
class Soulprint:
    identity: Dict[str, Any]
    principles: Dict[str, Any]
    goals: List[str]
    context: Dict[str, Any]

    @staticmethod
    def load(path: str) -> "Soulprint":
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except FileNotFoundError as e:
            raise ValueError(f"soulprint file not found: {path}") from e
        try:
            validated = _SoulprintModel.model_validate(data)
        except ValidationError as e:
            raise ValueError(f"invalid soulprint: {e.errors()}") from e
        return Soulprint(
            identity=validated.identity.model_dump(),
            principles=validated.principles.model_dump(),
            goals=list(validated.goals),
            context=dict(validated.context),
        )

    def voice_tag(self) -> str:
        name = self.identity.get("name", "Sam")
        tone = self.identity.get("tone", "neutral")
        return f"{name} · {tone}"

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List
from samos.core.soulprint import Soulprint

@dataclass
class Context:
    soulprint: Soulprint
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class UserMessage:
    text: str
    tags: List[str] = field(default_factory=list)

@dataclass
class Response:
    text: str
    meta: Dict[str, Any] = field(default_factory=dict)

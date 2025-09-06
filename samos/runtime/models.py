from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

@dataclass
class UserMessage:
    text: str
    user_id: Optional[str] = None

@dataclass
class Response:
    text: str
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Context:
    """
    Minimal context passed around the router/skills.
    Expects an object `soulprint` which may expose:
      - voice_tag() -> str           (used for friendly prefixes)
      - system_prompt() -> str       (optional: tone/system prompt)
    """
    soulprint: Any

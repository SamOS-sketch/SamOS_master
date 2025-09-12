# router.py (project root)
import re
from typing import Optional, Dict, Any

from samos.skills.image import ImageSkill  # ← use the samos package


class Router:
    """
    Super-light command router.
    Recognizes: 'Image: <prompt>' (case-insensitive on 'Image:')
    """

    IMAGE_RE = re.compile(r"^\s*image\s*:\s*(.+)$", re.IGNORECASE)

    def __init__(self, event_logger=None):
        self.event_logger = event_logger
        self.image_skill = ImageSkill(event_logger=event_logger)

    def route(
        self,
        user_text: str,
        *,
        img_provider: Optional[str] = None,
        size: str = "1024x1024",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        m = self.IMAGE_RE.match(user_text or "")
        if m:
            prompt = m.group(1).strip()
            return self.image_skill.run(
                prompt=prompt,
                size=size,
                provider_name=img_provider,
                session_id=session_id,
            )

        return {
            "status": "fail",
            "error": "Unrecognized command. Try: Image: a sunrise over London",
            "provider": "",
            "url": "",
            "image_id": "",
            "reference_used": None,
            "meta": {"input": user_text},
        }

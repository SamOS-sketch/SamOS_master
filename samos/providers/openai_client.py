import os
import time
import json
import logging
from typing import Any, Dict, List, Optional

import requests

log = logging.getLogger(__name__)


class OpenAIConfig:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout = int(os.getenv("OPENAI_REQUEST_TIMEOUT_SECS", "30"))
        self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "800"))
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
        self.log_latency = os.getenv("LOG_PROVIDER_LATENCY", "false").lower() == "true"

        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY missing")

    @property
    def chat_url(self) -> str:
        return f"{self.base}/chat/completions"

    @property
    def project_id(self) -> Optional[str]:
        # Project-scoped keys look like sk-proj-xxxxx...
        if self.api_key.startswith("sk-proj-"):
            # Extract project id if provided separately in env
            return os.getenv("OPENAI_PROJECT_ID")
        return None


class OpenAIClient:
    """Minimal OpenAI chat client with safe timeouts and retries."""

    def __init__(self, cfg: OpenAIConfig):
        self.cfg = cfg
        self._session = requests.Session()
        self._headers = {
            "Authorization": f"Bearer {self.cfg.api_key}",
            "Content-Type": "application/json",
        }
        # If project-scoped, add header
        if self.cfg.api_key.startswith("sk-proj-"):
            project = self.cfg.project_id
            if project:
                self._headers["OpenAI-Project"] = project

    def _should_retry(self, status: Optional[int]) -> bool:
        if status is None:
            return True
        if status == 429:
            return True
        if 500 <= status < 600:
            return True
        return False

    def chat(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        body = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature,
            "max_tokens": self.cfg.max_tokens,
        }

        attempts = 0
        start = time.time()

        while True:
            attempts += 1
            try:
                r = self._session.post(
                    self.cfg.chat_url,
                    headers=self._headers,
                    json=body,
                    timeout=self.cfg.timeout,
                )
                status = r.status_code
                if status >= 400:
                    if self._should_retry(status) and attempts < 3:
                        time.sleep(0.5 * (2 ** (attempts - 1)))
                        continue
                    r.raise_for_status()

                data = r.json()
                text = data["choices"][0]["message"]["content"]
                latency_ms = int((time.time() - start) * 1000)

                if self.cfg.log_latency:
                    log.info(
                        "provider=openai event=llm.ok latency_ms=%s model=%s",
                        latency_ms,
                        self.cfg.model,
                    )

                return {"ok": True, "text": text, "latency_ms": latency_ms}

            except requests.exceptions.RequestException as e:
                if attempts < 3:
                    time.sleep(0.5 * (2 ** (attempts - 1)))
                    continue
                latency_ms = int((time.time() - start) * 1000)
                if self.cfg.log_latency:
                    log.warning(
                        "provider=openai event=llm.fail latency_ms=%s error=%s",
                        latency_ms,
                        str(e),
                    )
                return {"ok": False, "error": str(e)}
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                latency_ms = int((time.time() - start) * 1000)
                if self.cfg.log_latency:
                    log.warning(
                        "provider=openai event=llm.fail latency_ms=%s error=parse_error",
                        latency_ms,
                    )
                return {"ok": False, "error": f"response.parse_error: {e}"}

# samos/config.py
from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    # ---- core ----
    SAMOS_PERSONA: str = Field("demo", pattern="^(demo|private)$")
    SAMOS_HOST: str = "127.0.0.1"
    SAMOS_PORT: int = 8000

    # ---- features ----
    IMAGE_PROVIDER: str = Field("stub", pattern="^(stub|openai|comfyui)$")

    # ---- cors ----
    CORS_ALLOW_ORIGINS: str = ""  # comma-separated list

    # ---- paths (can be overridden via env, else resolved per persona) ----
    SOULPRINT_PATH: str = ""
    DB_URL: str = ""  # if empty, we compute sqlite path per persona

    # Pydantic v2 settings config
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- derived helpers ----
    @property
    def cors_origins(self) -> list[str]:
        raw = (self.CORS_ALLOW_ORIGINS or "").strip()
        return [o.strip() for o in raw.split(",") if o.strip()]

    def resolved_soulprint(self) -> Path:
        if self.SOULPRINT_PATH:
            return Path(self.SOULPRINT_PATH).resolve()
        name = "soulprint.demo.yaml" if self.SAMOS_PERSONA == "demo" else "soulprint.private.yaml"
        return (ROOT / name).resolve()

    def resolved_db_url(self) -> str:
        if self.DB_URL:
            return self.DB_URL
        name = "demo.db" if self.SAMOS_PERSONA == "demo" else "samos.db"
        return f"sqlite:///{(ROOT / name).resolve()}"

    # ---- safety: demo must never load private soulprint ----
    @model_validator(mode="after")
    def _guard_demo_cannot_point_to_private(self):
        if (
            self.SAMOS_PERSONA == "demo"
            and self.SOULPRINT_PATH
            and Path(self.SOULPRINT_PATH).name == "soulprint.private.yaml"
        ):
            raise ValueError("demo persona cannot load private soulprint path")
        return self


# singleton
settings = Settings()


def assert_persona_safety():
    sp = settings.resolved_soulprint()
    if settings.SAMOS_PERSONA == "demo" and sp.name == "soulprint.private.yaml":
        raise RuntimeError("Safety: demo persona attempted to load private soulprint")

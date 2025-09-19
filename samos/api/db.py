import os
from datetime import datetime
from typing import Generator
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Float,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Persona-aware DB routing
from samos.core.persona import db_filename, get_persona

# Keep import for compatibility, but persona routing will be used unless DATABASE_URL is set explicitly.
try:
    from samos.api.settings import DB_URL as _SETTINGS_DB_URL  # noqa: F401
except Exception:
    _SETTINGS_DB_URL = None  # settings module optional / legacy


# ---------- Resolve DB URL (env > persona routing) ----------

def _resolve_db_url() -> str:
    """
    Decide which DB to use:
    1) DATABASE_URL environment variable (if set)
    2) Persona-based sqlite file under project root (private → samos.db, demo → demo.db)
    """
    env_url = os.getenv("DATABASE_URL")
    if env_url and env_url.strip():
        return env_url.strip()

    persona = get_persona()
    return f"sqlite:///./{db_filename(persona)}"


DB_URL = _resolve_db_url()


# ---------- SQLAlchemy base / engine / session ----------

Base = declarative_base()

_connect_args = {}
if DB_URL.startswith("sqlite"):
    _connect_args = {
        "check_same_thread": False,
        "timeout": 30,
    }

engine = create_engine(
    DB_URL,
    echo=False,
    future=True,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


# Optional: lightweight startup log
try:
    persona_label = get_persona().value
except Exception:
    persona_label = "unknown"

print(f"[SamOS] DB: {DB_URL}  |  Persona: {persona_label}")


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Models ----------

class Session(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True, index=True)
    mode = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    memories = relationship("Memory", back_populates="session", cascade="all, delete-orphan")
    images = relationship("Image", back_populates="session", cascade="all, delete-orphan")
    emms = relationship("EMM", back_populates="session", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="session", cascade="all, delete-orphan")


class Memory(Base):
    __tablename__ = "memories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    key = Column(String, index=True)
    value = Column(Text)
    meta_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    session = relationship("Session", back_populates="memories")


class Image(Base):
    """
    SamOS Image record (Phase A8b aligned)
    Canonical fields:
      - url (string)
      - prompt (text)
      - ref_used (bool, non-null)
      - drift_score (float, nullable)
      - provider (string, non-null, default 'stub')
      - tier (string, nullable)
      - latency_ms (int, nullable)
      - provenance (json-as-text; legacy/optional)
      - status (string; non-null; 'ok'|'failed')
      - meta_json (json-as-text; nullable)
      - local_path (text, nullable)
    """
    __tablename__ = "images"

    id = Column(String, primary_key=True, index=True, default=lambda: uuid4().hex)
    session_id = Column(String, ForeignKey("sessions.id"))

    # Core request/response fields
    url = Column(Text, nullable=False)                 # file:// or http(s)://
    prompt = Column(Text, nullable=False)
    ref_used = Column(Boolean, nullable=False, default=False)
    drift_score = Column(Float, nullable=True)

    # File location for serving
    local_path = Column(Text, nullable=True)

    # Provider provenance
    provider = Column(String(64), nullable=False, default="stub")   # openai | comfyui | stub
    tier = Column(String(32), nullable=True)                        # primary | recovery | fallback
    latency_ms = Column(Integer, nullable=True)
    provenance = Column(Text, nullable=True)

    # Status + metadata
    status = Column(String, nullable=False, default="ok")           # ok | failed
    meta_json = Column(Text, nullable=True, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)

    session = relationship("Session", back_populates="images")

    @property
    def reference_used(self) -> bool:
        return bool(self.ref_used)

    @reference_used.setter
    def reference_used(self, val: bool):
        self.ref_used = bool(val)


class EMM(Base):
    __tablename__ = "emms"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    type = Column(String)
    message = Column(Text)
    meta_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)

    session = relationship("Session", back_populates="emms")


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=True)
    ts = Column(DateTime, default=datetime.utcnow, nullable=False)
    kind = Column(String, nullable=False)     # e.g. session.start, mode.set, image.generate.ok
    message = Column(String, nullable=False)  # short summary
    meta_json = Column(Text, nullable=True)   # JSON string payload

    session = relationship("Session", back_populates="events")


# Helpful indexes
Index("idx_events_session_ts", Event.session_id, Event.ts)
Index("idx_events_kind_ts", Event.kind, Event.ts)
Index("idx_images_session_created", Image.session_id, Image.created_at)
Index("idx_memories_session_created", Memory.session_id, Memory.created_at)

# ---------- Optional metrics tables ----------

class MetricsCounter(Base):
    __tablename__ = "metrics_counters"
    key = Column(String, primary_key=True)
    value = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class MetricsBucket(Base):
    __tablename__ = "metrics_buckets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    metric = Column(String, index=True)
    period = Column(String)
    bucket_start = Column(DateTime)
    value = Column(Integer, default=0)


# ---------- init ----------

def init_db() -> None:
    """Create all tables if they don't exist, and harden SQLite settings."""
    Base.metadata.create_all(bind=engine)
    if DB_URL.startswith("sqlite"):
        with engine.begin() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.execute(text("PRAGMA synchronous=NORMAL;"))
            conn.execute(text("PRAGMA foreign_keys=ON;"))

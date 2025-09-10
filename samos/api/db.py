import os
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
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
    # Highest precedence: explicit DATABASE_URL from environment
    env_url = os.getenv("DATABASE_URL")
    if env_url and env_url.strip():
        return env_url.strip()

    # Persona-based default (private → samos.db, demo → demo.db)
    persona = get_persona()
    return f"sqlite:///./{db_filename(persona)}"


DB_URL = _resolve_db_url()


# ---------- SQLAlchemy base / engine / session ----------
Base = declarative_base()

# sqlite needs check_same_thread=False and benefits from a longer timeout
_connect_args = {}
if DB_URL.startswith("sqlite"):
    _connect_args = {
        "check_same_thread": False,
        "timeout": 30,  # wait up to 30s if the DB is briefly busy
    }

engine = create_engine(
    DB_URL,
    echo=False,
    future=True,
    connect_args=_connect_args,
    pool_pre_ping=True,  # refresh broken connections automatically
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


# Optional: lightweight startup log for visibility
try:
    # only import here to avoid circulars if app boot order changes
    persona_label = get_persona().value
except Exception:
    persona_label = "unknown"

print(f"[SamOS] DB: {DB_URL}  |  Persona: {persona_label}")


# Convenience generator (used by some routes)
def get_db():
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    memories = relationship(
        "Memory", back_populates="session", cascade="all, delete-orphan"
    )
    images = relationship(
        "Image", back_populates="session", cascade="all, delete-orphan"
    )
    emms = relationship("EMM", back_populates="session", cascade="all, delete-orphan")
    events = relationship(
        "Event", back_populates="session", cascade="all, delete-orphan"
    )


class Memory(Base):
    __tablename__ = "memories"  # ✅ correct plural name
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    key = Column(String, index=True)
    value = Column(Text)
    meta_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("Session", back_populates="memories")


class Image(Base):
    __tablename__ = "images"
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    prompt = Column(Text)
    from sqlalchemy import Column, Boolean, Float, String, Integer
    ref_used = Column(Boolean, nullable=False, default=False)
    drift_score = Column(Float, nullable=True)
    provider = Column(String(64), nullable=True)
    tier = Column(String(32), nullable=True)
    latency_ms = Column(Integer, nullable=True)

    # Phase 8 provenance fields
    provider = Column(
        String, nullable=True
    )  # e.g. openai | stability_api | comfyui | stub
    tier = Column(String, nullable=True)  # primary | recovery | fallback
    latency_ms = Column(
        Integer, nullable=True
    )  # measured latency for the successful attempt
    reference_used = Column(Boolean, default=False)  # whether reference image was used
    provenance = Column(Text, nullable=True)  # JSON-as-text for SQLite (extra details)

    # Existing fields
    url = Column(Text)
    status = Column(String, default="ok")  # ok | failed
    meta_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="images")


class EMM(Base):
    __tablename__ = "emms"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    type = Column(String)
    message = Column(Text)
    meta_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="emms")


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=True)
    ts = Column(DateTime, default=datetime.utcnow, nullable=False)
    kind = Column(
        String, nullable=False
    )  # e.g. session.start, mode.set, image.generate.ok
    message = Column(String, nullable=False)  # short summary
    meta_json = Column(Text, nullable=True)  # JSON string payload

    session = relationship("Session", back_populates="events")


# Helpful indexes
Index("idx_events_session_ts", Event.session_id, Event.ts)
Index("idx_events_kind_ts", Event.kind, Event.ts)

# ---------- Optional metrics tables (used by snapshot_service if present) ----------


class MetricsCounter(Base):
    __tablename__ = "metrics_counters"
    key = Column(String, primary_key=True)
    value = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MetricsBucket(Base):
    __tablename__ = "metrics_buckets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    metric = Column(String, index=True)  # e.g. image.ok
    period = Column(String)  # hour | day
    bucket_start = Column(DateTime)  # period start time
    value = Column(Integer, default=0)


# ---------- init ----------


def init_db():
    """Create all tables if they don't exist, and harden SQLite settings."""
    Base.metadata.create_all(bind=engine)
    # WAL + moderate sync for throughput + enforce FK integrity
    if DB_URL.startswith("sqlite"):
        with engine.begin() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.execute(text("PRAGMA synchronous=NORMAL;"))
            conn.execute(text("PRAGMA foreign_keys=ON;"))

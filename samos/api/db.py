import datetime
import os
from typing import Any, Dict

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def _resolve_db_url() -> str:
    """
    Deterministic DB selection order:
      1) DATABASE_URL env var (if set)
      2) sqlite:///./memory/samos.db if it exists (preferred)
      3) sqlite:///./samos.db fallback
    """
    env_url = os.getenv("DATABASE_URL")
    if env_url and env_url.strip():
        return env_url.strip()

    preferred = os.path.join(".", "memory", "samos.db")
    if os.path.exists(preferred):
        return "sqlite:///./memory/samos.db"

    return "sqlite:///./samos.db"


DB_URL = _resolve_db_url()

connect_args: Dict[str, Any] = {}
if DB_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DB_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _now_utc() -> datetime.datetime:
    return datetime.datetime.utcnow()


class Session(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=_now_utc, nullable=False)
    updated_at = Column(DateTime, default=_now_utc, nullable=False)
    mode = Column(String, default="work", nullable=True)
    persona = Column(String, default=None, nullable=True)
    meta_json = Column(Text, default=None, nullable=True)


class Memory(Base):
    __tablename__ = "memories"
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=True)
    scope = Column(String, index=True, nullable=True)
    key = Column(String, index=True, nullable=True)
    value = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now_utc, nullable=False)
    updated_at = Column(DateTime, default=_now_utc, nullable=False)


class EMM(Base):
    __tablename__ = "emm"
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=True)
    code = Column(String, index=True, nullable=True)
    tone = Column(String, index=True, nullable=True)
    text = Column(Text, nullable=True)
    meta_json = Column(Text, default=None, nullable=True)
    created_at = Column(DateTime, default=_now_utc, nullable=False)


class Image(Base):
    __tablename__ = "images"
    id = Column(String, primary_key=True, index=True)

    session_id = Column(String, index=True, nullable=False)

    url = Column(String, nullable=True)
    prompt = Column(Text, nullable=True)

    ref_used = Column(Boolean, default=False, nullable=True)
    drift_score = Column(Float, default=None, nullable=True)

    provider = Column(String, default=None, nullable=True)
    tier = Column(String, default=None, nullable=True)
    latency_ms = Column(Integer, default=None, nullable=True)

    provenance = Column(Text, default=None, nullable=True)
    status = Column(String, default=None, nullable=True)
    meta_json = Column(Text, default=None, nullable=True)

    created_at = Column(DateTime, default=_now_utc, nullable=False)

    local_path = Column(Text, default=None, nullable=True)
    mode = Column(String, default=None, nullable=True)
    alpha_id = Column(String, default=None, nullable=True)
    seed = Column(Integer, default=None, nullable=True)

class Event(Base):
    __tablename__ = "events"
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=True)
    type = Column(String, index=True, nullable=True)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now_utc, nullable=False)


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def db_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {"db_url": DB_URL}

    if DB_URL.startswith("sqlite:///./"):
        sqlite_path = DB_URL.replace("sqlite:///./", "./")
        info["sqlite_path"] = os.path.abspath(sqlite_path)
        info["sqlite_exists"] = os.path.exists(sqlite_path)
        if info["sqlite_exists"]:
            try:
                info["sqlite_size_bytes"] = os.path.getsize(sqlite_path)
            except Exception:
                info["sqlite_size_bytes"] = None

    try:
        insp = inspect(engine)
        info["tables"] = insp.get_table_names()
    except Exception:
        info["tables"] = []

    return info

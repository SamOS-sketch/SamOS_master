# migrations/env.py
from __future__ import annotations
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# --- Load your real models (NO duplicates) ---
from samos.api.db import Base

# Alembic Config object
config = context.config

# If alembic.ini has logging section, set it up
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use the real metadata for autogenerate
target_metadata = Base.metadata

def _db_url() -> str:
    """Build a SQLAlchemy URL from DB_PATH, defaulting to ./memory/samos.db."""
    db_path = os.getenv("DB_PATH", "./memory/samos.db")
    return db_path if db_path.startswith("sqlite:///") else f"sqlite:///{db_path}"

def run_migrations_offline():
    url = _db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _db_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


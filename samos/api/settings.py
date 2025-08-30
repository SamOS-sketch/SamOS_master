# settings.py

# Load .env files BEFORE reading env vars.
# 1) Try the CWD (project root)
# 2) Also force-load the .env that sits next to this file (samos/api/.env)
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# Load from working directory (e.g., C:\...\samos_phase4_scaffold\.env) if present
load_dotenv(find_dotenv(usecwd=True))

# Also load the .env that lives alongside this file (samos/api/.env)
api_env = Path(__file__).resolve().parent / ".env"
if api_env.exists():
    load_dotenv(dotenv_path=api_env, override=True)

import os

# ---- Database ----
DB_URL = os.getenv("DB_URL", "sqlite:///./samos.db")

# ---- Default Mode ----
SAM_MODE_DEFAULT = os.getenv("SAM_MODE_DEFAULT", "work")

# ---- Image Provider ----
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "openai")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
REFERENCE_IMAGE_ALPHA = os.getenv("REFERENCE_IMAGE_ALPHA", "")

# ---- Phase 7: Persistence & Recovery settings ----
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-me")
AUTO_RESTORE_LAST_SNAPSHOT = (
    os.getenv("AUTO_RESTORE_LAST_SNAPSHOT", "false").lower() == "true"
)
FORCE_ON_NONEMPTY = os.getenv("FORCE_ON_NONEMPTY", "false").lower() == "true"
SNAPSHOT_DIR = os.getenv("SNAPSHOT_DIR", "./snapshots")

# Bump when snapshot structure changes
SCHEMA_VERSION = 3

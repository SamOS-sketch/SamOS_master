# samos/api/health.py
from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> Dict[str, Any]:
    """
    Minimal health check.
    Purpose: confirm the API process is running and able to respond.
    No external dependencies. No side effects.
    """
    return {
        "ok": True,
        "status": "alive"
    }

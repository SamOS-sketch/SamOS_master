# samos/core/persona.py
import os
from enum import Enum


class Persona(str, Enum):
    PRIVATE = "private"
    DEMO = "demo"

DEFAULT_PERSONA = Persona.PRIVATE

def get_persona() -> Persona:
    val = os.getenv("SAMOS_PERSONA", "private").strip().lower()
    if val in ("private", "demo"):
        return Persona(val)
    return DEFAULT_PERSONA

def db_filename(persona: Persona) -> str:
    return "samos.db" if persona == Persona.PRIVATE else "demo.db"

def describe_persona() -> str:
    p = get_persona()
    return f"Persona: {p.value}"

"""App settings, read from environment variables.

Secrets like API keys live in environment variables (or a local .env file),
never in the code itself.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# backend/app/config.py -> parents[2] is the project root (mise/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Recipe photos uploaded by the user. Kept next to the database, never sent anywhere.
PHOTOS_DIR = Path(os.getenv("PHOTOS_DIR") or DATA_DIR / "photos")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'mise.db'}")

# Used by AI ingredient recognition (and the substitution assistant in M6). None if not set.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") or None

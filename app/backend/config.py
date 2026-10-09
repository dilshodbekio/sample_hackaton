import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR.parent / ".env")

AI_MOCK = os.getenv("AI_MOCK", "true").strip().lower() in ("1", "true", "yes")
AI_URL = (os.getenv("AI_URL") or "http://localhost:8001").rstrip("/")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN") or "http://localhost:5173"

DB_PATH = BASE_DIR / "app.db"

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
HISTORY_LIMIT = 6

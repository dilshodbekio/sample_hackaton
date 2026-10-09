import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

_data_dir = Path(os.getenv("DATA_DIR") or "./data")
DATA_DIR = _data_dir if _data_dir.is_absolute() else (BASE_DIR / _data_dir).resolve()
UPLOADS_DIR = DATA_DIR / "uploads"
CHROMA_DIR = DATA_DIR / "chroma"
DOCUMENTS_FILE = DATA_DIR / "documents.json"

# Embedding: gemini-embedding-2 task_type ni qo'llamaydi, vazifa matn prefiksi bilan beriladi
# (hujjat: "title: ... | text: ...", savol: "task: search result | query: ...").
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIM = 768
EMBEDDING_BATCH_SIZE = 100  # API chegarasi: bitta so'rovda ko'pi bilan 100 ta

CHROMA_COLLECTION = "chunks"

# LLM (models.list bilan tekshirilgan; gemini-3.7/3.8-flash da 503/504 va sekin birinchi token kuzatildi)
LLM_MODEL = "gemini-3.5-flash"
LLM_THINKING_LEVEL = "MINIMAL"  # tezlik uchun; bu model MINIMAL ni qo'llaydi (3.8-flash qo'llamaydi)
LLM_TEMPERATURE = 0.2

# Retrieval
TOP_K = 5
# cosine masofasi; shundan KATTA bo'laklar tashlanadi. namuna_nizom.pdf o'lchovi: tegishli savollar top-1 0.18–0.25,
# chegaradagi (hujjatda yo'q, mavzu yaqin) 0.28–0.36, umuman aloqasiz 0.44–0.50.
MAX_DISTANCE = 0.40  # vaqtincha, faqat namuna_nizom.pdf bo'yicha o'lchangan
MAX_QUESTION_CHARS = 1000
MAX_BODY_BYTES = 64 * 1024  # /ask/stream so'rov body'si chegarasi
QUERY_TIMEOUT_MS = 15_000  # savol embeddingi: foydalanuvchi kutib turadi, qisqa timeout
QUERY_RETRY_ATTEMPTS = 2
MAX_HISTORY = 6
SNIPPET_CHARS = 200
NOT_FOUND_TEXT = "Yuklangan hujjatlarda bu savolga javob topilmadi."

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
MIN_CHUNK_CHARS = 30
MIN_DOC_TEXT_CHARS = 200

for _d in (DATA_DIR, UPLOADS_DIR, CHROMA_DIR):
    _d.mkdir(parents=True, exist_ok=True)

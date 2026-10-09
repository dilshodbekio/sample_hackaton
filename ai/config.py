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
# cosine masofasi; shundan KATTA bo'laklar tashlanadi. nizom_572.pdf (44 bet, 192 bo'lak) o'lchovi, top-1..top-5:
# tegishli savollar 0.19–0.27, chegaradagi (mavzu yaqin, hujjatda yo'q) 0.28–0.36, umuman aloqasiz 0.41–0.45.
# Chegaradagi savollar LLM'ga boradi (u "topilmadi" deydi), aloqasizlari LLM'siz kesiladi.
# namuna_nizom.pdf (4 bet) bo'yicha ham mos: tegishli ≤ 0.25, chegara 0.28–0.36, aloqasiz ≥ 0.44.
MAX_DISTANCE = 0.38
MAX_QUESTION_CHARS = 1000
MAX_BODY_BYTES = 64 * 1024  # /ask/stream so'rov body'si chegarasi
QUERY_TIMEOUT_MS = 15_000  # savol embeddingi: foydalanuvchi kutib turadi, qisqa timeout
QUERY_RETRY_ATTEMPTS = 2
MAX_HISTORY = 6
SNIPPET_CHARS = 200
MAX_SOURCES = 3  # sources: ko'pi bilan shuncha bet
SOURCES_MARGIN = 0.05  # sources: eng yaxshi masofadan shuncha ortiq bo'lmagan bo'laklar
NOT_FOUND_TEXT = "Yuklangan hujjatlarda bu savolga javob topilmadi."

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
MIN_CHUNK_CHARS = 30
MIN_DOC_TEXT_CHARS = 200

for _d in (DATA_DIR, UPLOADS_DIR, CHROMA_DIR):
    _d.mkdir(parents=True, exist_ok=True)

"""Gemini embedding. Hujjat va savol uchun prefikslar shu yerda (gemini-embedding-2 task_type ni qo'llamaydi)."""

import logging
import re
import threading
import time

from google import genai
from google.genai import errors, types

from config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    GEMINI_API_KEY,
    QUERY_RETRY_ATTEMPTS,
    QUERY_TIMEOUT_MS,
)

log = logging.getLogger("ai.embeddings")

_lock = threading.Lock()
_client: genai.Client | None = None
_query_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    with _lock:
        if _client is None:
            if not GEMINI_API_KEY:
                raise RuntimeError("GEMINI_API_KEY .env da topilmadi")
            _client = genai.Client(
                api_key=GEMINI_API_KEY,
                http_options=types.HttpOptions(
                    timeout=60_000,
                    # 429 va 5xx da eksponensial kutish bilan qayta urinish
                    retry_options=types.HttpRetryOptions(attempts=4, initial_delay=1.0, max_delay=20.0),
                ),
            )
    return _client


def get_query_client() -> genai.Client:
    """Savol embeddingi uchun alohida klient: ingest'dagidan qisqa timeout va kam urinish."""
    global _query_client
    with _lock:
        if _query_client is None:
            if not GEMINI_API_KEY:
                raise RuntimeError("GEMINI_API_KEY .env da topilmadi")
            _query_client = genai.Client(
                api_key=GEMINI_API_KEY,
                http_options=types.HttpOptions(
                    timeout=QUERY_TIMEOUT_MS,
                    retry_options=types.HttpRetryOptions(attempts=QUERY_RETRY_ATTEMPTS, initial_delay=1.0, max_delay=4.0),
                ),
            )
    return _query_client


def document_input(text: str, title: str | None = None) -> str:
    return f"title: {title or 'none'} | text: {text}"


def query_input(text: str) -> str:
    return f"task: search result | query: {text}"


RATE_LIMIT_WAITS = 6  # ingest: kunlik/daqiqalik kvota tugasa serverning retryDelay qiymatini shuncha marta kutamiz
_RETRY_DELAY = re.compile(r"retry in ([\d.]+)s|'retryDelay': '([\d.]+)s'")


def _retry_delay(exc: errors.APIError) -> float:
    m = _RETRY_DELAY.search(str(exc))
    return float(m.group(1) or m.group(2)) if m else 30.0


def embed_texts(texts: list[str], client: genai.Client | None = None) -> list[list[float]]:
    """Har bir matnga alohida vektor. Diqqat: contents=[str, ...] berilsa gemini-embedding-2
    hammasini BITTA vektorga birlashtiradi, shuning uchun har biri alohida Content qilinadi."""
    own_client = client is None  # True: ingest yo'li
    client = client or get_client()
    config = types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM)
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        contents = [types.Content(parts=[types.Part(text=t)]) for t in batch]
        for attempt in range(RATE_LIMIT_WAITS + 1):
            try:
                resp = client.models.embed_content(model=EMBEDDING_MODEL, contents=contents, config=config)
                break
            except errors.APIError as e:
                # Free-tier: daqiqasiga ~100 ta embed so'rovi. Faqat ingest (client berilmagan) kutadi,
                # savol yo'lida foydalanuvchi kutib turgani uchun darhol xato beriladi.
                if e.code != 429 or not own_client or attempt == RATE_LIMIT_WAITS:
                    raise
                wait = _retry_delay(e) + 1
                log.warning("embedding kvotasi (429): %.0f s kutiladi (%d/%d)", wait, attempt + 1, RATE_LIMIT_WAITS)
                time.sleep(wait)
        if not resp.embeddings or len(resp.embeddings) != len(batch):
            got = len(resp.embeddings or [])
            raise RuntimeError(f"Embedding soni mos emas: {len(batch)} ta so'raldi, {got} ta keldi")
        vectors.extend(e.values for e in resp.embeddings)
    return vectors

"""Gemini embedding. Hujjat va savol uchun prefikslar shu yerda (gemini-embedding-2 task_type ni qo'llamaydi)."""

import threading

from google import genai
from google.genai import types

from config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    GEMINI_API_KEY,
    QUERY_RETRY_ATTEMPTS,
    QUERY_TIMEOUT_MS,
)

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


def embed_texts(texts: list[str], client: genai.Client | None = None) -> list[list[float]]:
    """Har bir matnga alohida vektor. Diqqat: contents=[str, ...] berilsa gemini-embedding-2
    hammasini BITTA vektorga birlashtiradi, shuning uchun har biri alohida Content qilinadi."""
    client = client or get_client()
    config = types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM)
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        resp = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=[types.Content(parts=[types.Part(text=t)]) for t in batch],
            config=config,
        )
        if not resp.embeddings or len(resp.embeddings) != len(batch):
            got = len(resp.embeddings or [])
            raise RuntimeError(f"Embedding soni mos emas: {len(batch)} ta so'raldi, {got} ta keldi")
        vectors.extend(e.values for e in resp.embeddings)
    return vectors

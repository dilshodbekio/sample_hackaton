"""AI_MOCK=true rejimi: ai/ servisini chaqirmasdan soxta javoblar."""

import asyncio
import time
import uuid

from db import now_iso
from sse import format_event

TOKEN_DELAY = 0.05
PROCESSING_SECONDS = 5

MOCK_ANSWER = (
    "Bu soxta (mock) javob. Oliy toifa uchun o'qituvchi kamida besh yillik pedagogik "
    "stajga ega bo'lishi, oxirgi attestatsiyadan keyin malaka oshirish kursini tamomlagan "
    "bo'lishi va ochiq dars natijalari bo'yicha ijobiy baho olgan bo'lishi kerak. "
    "Batafsil ma'lumot nizomning tegishli bo'limida keltirilgan."
)
NOT_FOUND_ANSWER = "Yuklangan hujjatlarda bu savolga javob topilmadi."
MOCK_SOURCES = [
    {
        "doc_id": "doc_mock",
        "doc_name": "Namuna.pdf",
        "page": 1,
        "snippet": "Oliy toifa uchun talablar: pedagogik staj kamida 5 yil, malaka oshirish kursi...",
    }
]


def _words(text: str) -> list[str]:
    parts = text.split(" ")
    return [p + " " for p in parts[:-1]] + [parts[-1]]


async def ask_stream(question: str):
    if "test-xato" in question:
        for word in _words("Javob tayyorlanmoqda, lekin")[:3]:
            await asyncio.sleep(TOKEN_DELAY)
            yield format_event("token", {"text": word})
        yield format_event("error", {"message": "Soxta xato: AI servisida muammo yuz berdi (test-xato)."})
        return

    not_found = "test-topilmadi" in question
    for word in _words(NOT_FOUND_ANSWER if not_found else MOCK_ANSWER):
        await asyncio.sleep(TOKEN_DELAY)
        yield format_event("token", {"text": word})
    yield format_event("sources", {"sources": [] if not_found else MOCK_SOURCES})
    yield format_event("done", {})


# --- Hujjatlar (xotirada; servis qayta ishga tushsa yo'qoladi, mock uchun yetarli) ---

_documents: dict[str, dict] = {}


def _current(doc: dict) -> dict:
    ready = time.monotonic() - doc["_started"] >= PROCESSING_SECONDS
    return {
        "id": doc["id"],
        "name": doc["name"],
        "status": "ready" if ready else "processing",
        "pages": 10 if ready else None,
        "chunks": 25 if ready else None,
        "error": None,
        "created_at": doc["created_at"],
    }


def create_document(name: str) -> dict:
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    _documents[doc_id] = {"id": doc_id, "name": name, "created_at": now_iso(), "_started": time.monotonic()}
    return {"id": doc_id, "name": name, "status": "processing"}


def list_documents() -> list[dict]:
    docs = [_current(d) for d in _documents.values()]
    for d in docs:
        d.pop("error")
    return sorted(docs, key=lambda d: d["created_at"], reverse=True)


def get_document(doc_id: str) -> dict | None:
    doc = _documents.get(doc_id)
    return _current(doc) if doc else None


def delete_document(doc_id: str) -> bool:
    return _documents.pop(doc_id, None) is not None

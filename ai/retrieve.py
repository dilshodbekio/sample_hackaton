"""Retrieve: savolni embedding qilish va faqat 'ready' hujjatlar bo'laklaridan eng yaqinlarini topish."""

import logging
from dataclasses import dataclass

import store
from config import MAX_DISTANCE, TOP_K
from embeddings import embed_texts, get_query_client, query_input
from ingest import normalize_text
from vectordb import get_collection

log = logging.getLogger("ai.retrieve")


class RequestError(Exception):
    """So'rov bilan bog'liq xato; xabar to'g'ridan-to'g'ri foydalanuvchiga ko'rsatiladi."""


@dataclass
class Hit:
    doc_id: str
    doc_name: str
    page: int
    text: str
    distance: float


def build_queries(question: str, history: list[dict]) -> list[str]:
    """Qidiruv matnlari. history bo'lsa ikkita: faqat joriy savol (mustaqil savol uchun) va
    oldingi foydalanuvchi savoli + joriy savol (keyingi savol uchun). Qo'shimcha LLM chaqiruvisiz."""
    for msg in reversed(history):
        if msg["role"] == "user":
            return [question, f"{msg['content'][:500]}\n{question}"]
    return [question]


def resolve_docs(doc_ids: list[str] | None) -> tuple[list[str], int]:
    """Qidiriladigan 'ready' hujjat id lari va ulardagi bo'laklar soni."""
    ready = {d["id"]: d for d in store.list_all() if d["status"] == "ready"}
    if not ready:
        raise RequestError("Hozircha tayyor hujjat yo'q. Avval PDF hujjat yuklang va ishlov tugashini kuting.")
    if doc_ids:
        bad = [i for i in doc_ids if i not in ready]
        if bad:
            raise RequestError("Tanlangan hujjat topilmadi yoki hali tayyor emas: " + ", ".join(bad))
        ids = list(dict.fromkeys(doc_ids))
    else:
        ids = list(ready)
    return ids, sum(ready[i].get("chunks") or 0 for i in ids)


def search(queries: list[str], doc_ids: list[str], total_chunks: int) -> list[Hit]:
    """Har bo'lak uchun barcha qidiruv matnlari ichidagi eng kichik masofa; masofa o'sish tartibida, ko'pi bilan TOP_K."""
    n = min(TOP_K, total_chunks)
    if n < 1:
        return []
    inputs = [query_input(normalize_text(q)) for q in queries]
    vectors = embed_texts(inputs, client=get_query_client())  # bitta so'rov, har matn alohida Content
    where = {"doc_id": doc_ids[0]} if len(doc_ids) == 1 else {"doc_id": {"$in": doc_ids}}
    res = get_collection().query(
        query_embeddings=vectors, n_results=n, where=where, include=["documents", "metadatas", "distances"]
    )
    best: dict[str, Hit] = {}
    for q in range(len(vectors)):
        for chunk_id, text, m, dist in zip(res["ids"][q], res["documents"][q], res["metadatas"][q], res["distances"][q]):
            if chunk_id not in best or dist < best[chunk_id].distance:
                best[chunk_id] = Hit(m["doc_id"], m["doc_name"], int(m["page"]), text, float(dist))
    return sorted(best.values(), key=lambda h: h.distance)[:n]


def retrieve(question: str, history: list[dict], doc_ids: list[str] | None) -> list[Hit]:
    """Sinxron (threadpool'da chaqiriladi). Chegaradan o'tgan bo'laklar relevantlik tartibida."""
    ids, total = resolve_docs(doc_ids)
    hits = search(build_queries(question, history), ids, total)
    kept = [h for h in hits if h.distance <= MAX_DISTANCE]
    log.info("retrieve: %d/%d bo'lak chegaradan o'tdi (masofalar: %s)", len(kept), len(hits), [round(h.distance, 3) for h in hits])
    return kept

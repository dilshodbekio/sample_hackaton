"""Hujjat holatlari: DATA_DIR/documents.json. Barcha o'qish/yozish lock ostida, yozish atomik."""

import json
import os
import tempfile
import threading
from datetime import datetime, timezone

from config import DOCUMENTS_FILE

_lock = threading.Lock()

RESTART_ERROR = "Servis qayta ishga tushdi, ishlov tugamadi. Hujjatni qayta yuklang."


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read() -> dict:
    if not DOCUMENTS_FILE.exists():
        return {}
    with open(DOCUMENTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _write(docs: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=DOCUMENTS_FILE.parent, prefix=".documents.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, DOCUMENTS_FILE)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def create(doc_id: str, name: str) -> dict:
    doc = {
        "id": doc_id,
        "name": name,
        "status": "processing",
        "pages": None,
        "chunks": None,
        "error": None,
        "created_at": now_iso(),
    }
    with _lock:
        docs = _read()
        docs[doc_id] = doc
        _write(docs)
    return dict(doc)


def get(doc_id: str) -> dict | None:
    with _lock:
        doc = _read().get(doc_id)
    return dict(doc) if doc else None


def list_all() -> list[dict]:
    with _lock:
        docs = list(_read().values())
    # created_at soniya aniqligida: bir xil vaqtlilar orasida keyin qo'shilgani (dict tartibi) oldinda
    docs.reverse()
    return sorted(docs, key=lambda d: d["created_at"], reverse=True)


def update(doc_id: str, **fields) -> bool:
    """Yozuv hali bor bo'lsa yangilaydi. O'chirilgan bo'lsa False qaytaradi."""
    with _lock:
        docs = _read()
        if doc_id not in docs:
            return False
        docs[doc_id].update(fields)
        _write(docs)
    return True


def delete(doc_id: str) -> bool:
    with _lock:
        docs = _read()
        if docs.pop(doc_id, None) is None:
            return False
        _write(docs)
    return True


def fail_interrupted() -> list[str]:
    """Servis ishga tushganda: 'processing' da qolib ketganlarni 'failed' qiladi. Ularning id lari qaytadi."""
    with _lock:
        docs = _read()
        ids = []
        for doc in docs.values():
            if doc["status"] == "processing":
                doc.update(status="failed", error=RESTART_ERROR)
                ids.append(doc["id"])
        if ids:
            _write(docs)
    return ids

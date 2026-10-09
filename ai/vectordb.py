import threading

import chromadb

from config import CHROMA_COLLECTION, CHROMA_DIR

_lock = threading.Lock()
_collection = None
_client = None


def get_collection():
    """Embedding'larni doim o'zimiz beramiz: embedding_function=None (Chroma standart modeli ishlatilmaydi)."""
    global _collection, _client
    with _lock:
        if _collection is None:
            _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            _collection = _client.get_or_create_collection(
                name=CHROMA_COLLECTION,
                embedding_function=None,
                metadata={"hnsw:space": "cosine"},
            )
    return _collection


def delete_document_chunks(doc_id: str) -> None:
    get_collection().delete(where={"doc_id": doc_id})


def add_chunks(ids: list[str], texts: list[str], metas: list[dict], vectors: list[list[float]]) -> None:
    """Chroma max_batch_size chegarasidan oshmaslik uchun paketlab yozadi."""
    collection = get_collection()
    step = _client.get_max_batch_size()
    for i in range(0, len(ids), step):
        collection.add(
            ids=ids[i : i + step],
            documents=texts[i : i + step],
            metadatas=metas[i : i + step],
            embeddings=vectors[i : i + step],
        )

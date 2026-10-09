"""Ingest: PDF o'qish -> matnni normallashtirish -> betma-bet bo'laklash -> embedding -> Chroma."""

import io
import logging
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

import store
from config import CHUNK_OVERLAP, CHUNK_SIZE, MIN_CHUNK_CHARS, MIN_DOC_TEXT_CHARS
from embeddings import document_input, embed_texts
from vectordb import add_chunks, delete_document_chunks

log = logging.getLogger("ai.ingest")

SCANNED_ERROR = "PDF'da o'qiladigan matn topilmadi (skaner qilingan bo'lishi mumkin)"


class IngestError(Exception):
    """Foydalanuvchiga ko'rsatiladigan tushunarli xabar bilan."""


# --- Matnni normallashtirish (savolga ham qo'llanadi) ---

# ʻ U+02BB, ʼ U+02BC, ‘ U+2018, ’ U+2019, ` U+0060 -> '
_APOSTROPHES = str.maketrans({"ʻ": "'", "ʼ": "'", "‘": "'", "’": "'", "`": "'"})
_HYPHEN_BREAK = re.compile(r"(\w)-[ \t]*\n[ \t]*(\w)")
_INLINE_SPACE = re.compile(r"[^\S\n]+")  # \n dan boshqa barcha bo'shliqlar (tab, NBSP, ...)
_SPACE_AROUND_NL = re.compile(r" *\n *")
_MANY_NL = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_APOSTROPHES)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHEN_BREAK.sub(r"\1-\2", text)  # "ilmiy-\nuslubiy" -> "ilmiy-uslubiy" (chiziqcha saqlanadi)
    text = _INLINE_SPACE.sub(" ", text)
    text = _SPACE_AROUND_NL.sub("\n", text)
    text = _MANY_NL.sub("\n\n", text)  # paragraf ajratgichi \n\n saqlanadi
    return text.strip()


# --- Bo'laklash ---

_SENTENCE_END = re.compile(r"[.!?;:]\s")


def _find_break(text: str, lo: int, hi: int) -> int:
    """[lo, hi) oralig'ida eng yaxshi kesish nuqtasi: paragraf > qator > gap oxiri > bo'shliq."""
    window = text[lo:hi]
    for sep in ("\n\n", "\n"):
        pos = window.rfind(sep)
        if pos != -1:
            return lo + pos
    ends = list(_SENTENCE_END.finditer(window))
    if ends:
        return lo + ends[-1].start() + 1
    pos = window.rfind(" ")
    if pos != -1:
        return lo + pos
    return hi


def split_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if len(text) <= size:
        return [text] if len(text) >= MIN_CHUNK_CHARS else []
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            # chegarani oxirgi ~200 belgi ichidan qidiramiz, lekin overlap'dan keyin (oldinga siljish kafolati)
            lo = max(start + overlap + 1, end - 200)
            end = _find_break(text, lo, end)
        chunk = text[start:end].strip()
        if len(chunk) >= MIN_CHUNK_CHARS:
            chunks.append(chunk)
        if end >= n:
            break
        next_start = end - overlap
        # so'z o'rtasidan boshlamaslik uchun keyingi bo'shliqqa suriladi
        sp = text.find(" ", next_start, end)
        next_start = sp + 1 if sp != -1 else next_start
        start = max(next_start, start + 1)
    return chunks


# --- PDF ---

def read_pdf_pages(path: Path) -> list[str]:
    """Har bet uchun normallashtirilgan matn (indeks 0 = 1-bet)."""
    try:
        data = path.read_bytes()  # faylni darhol yopamiz (Windows'da ochiq fayl o'chmaydi)
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise IngestError("PDF parol bilan himoyalangan, uni o'qib bo'lmadi")
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            try:
                pages.append(normalize_text(page.extract_text() or ""))
            except Exception:
                log.warning("%s: %d-betdan matn olinmadi, o'tkazib yuborildi", path.name, i, exc_info=True)
                pages.append("")
        return pages
    except IngestError:
        raise
    except Exception as e:
        raise IngestError("PDF faylni o'qib bo'lmadi (fayl buzilgan bo'lishi mumkin)") from e


def build_chunks(doc_id: str, doc_name: str, pages: list[str]) -> tuple[list[str], list[str], list[dict]]:
    ids, texts, metas = [], [], []
    for page_no, page_text in enumerate(pages, start=1):
        for n, chunk in enumerate(split_text(page_text)):
            ids.append(f"{doc_id}_p{page_no}_c{n}")
            texts.append(chunk)
            metas.append({"doc_id": doc_id, "doc_name": doc_name, "page": page_no})
    return ids, texts, metas


def process_document(doc_id: str, doc_name: str, path: Path) -> None:
    """Fon ishlovi (threadpool'da). Har qanday xato -> status failed + tushunarli error."""
    try:
        pages = read_pdf_pages(path)
        total_chars = sum(len(p) for p in pages)
        ids, texts, metas = build_chunks(doc_id, doc_name, pages)
        if total_chars < MIN_DOC_TEXT_CHARS or not ids:
            raise IngestError(SCANNED_ERROR)

        try:
            vectors = embed_texts([document_input(t, doc_name) for t in texts])
        except Exception as e:
            raise IngestError("Embedding xizmatida xato. Keyinroq qayta urinib ko'ring.") from e

        if store.get(doc_id) is None:
            log.info("%s: ishlov paytida o'chirilgan, saqlanmaydi", doc_id)
            return
        try:
            add_chunks(ids, texts, metas, vectors)
        except Exception as e:
            raise IngestError("Vektor bazaga yozishda xato") from e

        if not store.update(doc_id, status="ready", pages=len(pages), chunks=len(ids), error=None):
            # yozish paytida DELETE bo'lgan: qoldiq bo'laklarni tozalaymiz
            delete_document_chunks(doc_id)
            return
        log.info("%s: ready (%d bet, %d bo'lak)", doc_id, len(pages), len(ids))
    except Exception as e:
        message = str(e) if isinstance(e, IngestError) else "Hujjatni qayta ishlashda kutilmagan xato"
        log.error("%s: failed: %s", doc_id, message, exc_info=True)
        try:
            delete_document_chunks(doc_id)  # qisman yozilgan bo'laklar qolmasin
        except Exception:
            log.exception("%s: bo'laklarni tozalashda xato", doc_id)
        store.update(doc_id, status="failed", error=message)

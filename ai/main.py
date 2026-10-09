import asyncio
import json
import logging
import os
import secrets
from contextlib import aclosing, asynccontextmanager
from pathlib import PurePath

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

import store
from config import MAX_BODY_BYTES, MAX_HISTORY, MAX_QUESTION_CHARS, MAX_UPLOAD_BYTES, MAX_SOURCES, NOT_FOUND_TEXT, SNIPPET_CHARS, SOURCES_MARGIN, UPLOADS_DIR
from generate import EMPTY_MESSAGE, stream_answer, user_message
from ingest import process_document
from retrieve import Hit, RequestError, retrieve
from vectordb import delete_document_chunks, get_collection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ai")

READ_CHUNK = 1024 * 1024
TOO_LARGE = "Fayl juda katta (ko'pi bilan 20 MB)"
NOT_PDF = "Faqat PDF fayl qabul qilinadi"


@asynccontextmanager
async def lifespan(app: FastAPI):
    failed_ids = await run_in_threadpool(store.fail_interrupted)
    for doc_id in failed_ids:
        try:  # qisman yozilgan bo'laklar retrieve'ga tushmasin
            await run_in_threadpool(delete_document_chunks, doc_id)
        except Exception:
            log.exception("%s: bo'laklarni tozalashda xato", doc_id)
    if failed_ids:
        log.warning("%d ta tugallanmagan hujjat 'failed' qilindi", len(failed_ids))
    await run_in_threadpool(get_collection)
    yield


app = FastAPI(title="Attestatsiya AI", lifespan=lifespan)


def _public(doc: dict, with_error: bool = True) -> dict:
    keys = ["id", "name", "status", "pages", "chunks"] + (["error"] if with_error else []) + ["created_at"]
    return {k: doc.get(k) for k in keys}


def _pdf_path(doc_id: str):
    return UPLOADS_DIR / f"{doc_id}.pdf"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/documents", status_code=202)
async def upload_document(request: Request, background: BackgroundTasks, file: UploadFile | None = File(None)):
    if file is None:
        raise HTTPException(400, "'file' maydonida PDF fayl yuborilmadi")

    name = PurePath((file.filename or "").replace("\\", "/")).name.strip() or "document.pdf"
    is_pdf_name = name.lower().endswith(".pdf")
    is_pdf_type = (file.content_type or "").lower() == "application/pdf"
    if not (is_pdf_name or is_pdf_type):
        raise HTTPException(415, NOT_PDF)

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_UPLOAD_BYTES + 64 * 1024:
        raise HTTPException(413, TOO_LARGE)

    doc_id = f"doc_{secrets.token_hex(4)}"
    path = _pdf_path(doc_id)
    tmp = path.with_suffix(".part")
    size = 0
    header = b""
    try:
        with open(tmp, "wb") as out:
            while chunk := await file.read(READ_CHUNK):
                if not header:
                    header = chunk[:5]
                    if header != b"%PDF-":
                        raise HTTPException(415, NOT_PDF)
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, TOO_LARGE)
                await run_in_threadpool(out.write, chunk)
        if size == 0:
            raise HTTPException(415, NOT_PDF)
        await run_in_threadpool(os.replace, tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()

    doc = await run_in_threadpool(store.create, doc_id, name)
    background.add_task(process_document, doc_id, name, path)  # sync -> threadpool'da ishlaydi
    log.info("%s: yuklandi (%s, %d bayt)", doc_id, name, size)
    return {"id": doc["id"], "name": doc["name"], "status": doc["status"]}


@app.get("/documents")
async def list_documents():
    docs = await run_in_threadpool(store.list_all)
    return [_public(d, with_error=False) for d in docs]


@app.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    doc = await run_in_threadpool(store.get, doc_id)
    if doc is None:
        raise HTTPException(404, "Hujjat topilmadi")
    return _public(doc)


def _delete_document(doc_id: str) -> bool:
    if store.get(doc_id) is None:
        return False
    delete_document_chunks(doc_id)
    try:
        _pdf_path(doc_id).unlink(missing_ok=True)
    except OSError:
        log.warning("%s: PDF faylni o'chirib bo'lmadi", doc_id, exc_info=True)
    store.delete(doc_id)
    return True


@app.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: str):
    try:
        found = await run_in_threadpool(_delete_document, doc_id)
    except Exception:
        log.error("%s: o'chirishda xato", doc_id, exc_info=True)
        raise HTTPException(500, "Hujjatni o'chirib bo'lmadi, birozdan keyin qayta urinib ko'ring") from None
    if not found:
        raise HTTPException(404, "Hujjat topilmadi")
    log.info("%s: o'chirildi", doc_id)
    return Response(status_code=204)


# --- POST /ask/stream ---

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
HISTORY_ITEM_CHARS = 2000


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def parse_ask(body) -> tuple[str, list[str] | None, list[dict]]:
    """So'rov body'sini tekshiradi. Noto'g'ri bo'lsa RequestError (HTTP 422 emas, event: error bo'ladi)."""
    if not isinstance(body, dict):
        raise RequestError("So'rov JSON obyekt bo'lishi kerak")
    question = body.get("question")
    if not isinstance(question, str) or not question.strip():
        raise RequestError("Savol bo'sh bo'lmasligi kerak")
    question = question.strip()
    if len(question) > MAX_QUESTION_CHARS:
        raise RequestError(f"Savol juda uzun (ko'pi bilan {MAX_QUESTION_CHARS} belgi)")

    doc_ids = body.get("doc_ids")
    if doc_ids is not None and not (isinstance(doc_ids, list) and all(isinstance(i, str) for i in doc_ids)):
        raise RequestError("doc_ids matnlar ro'yxati bo'lishi kerak")

    raw_history = body.get("history")
    history: list[dict] = []
    if raw_history is not None:
        if not isinstance(raw_history, list):
            raise RequestError("history xabarlar ro'yxati bo'lishi kerak")
        for m in raw_history[-MAX_HISTORY:]:
            if not (
                isinstance(m, dict)
                and m.get("role") in ("user", "assistant")
                and isinstance(m.get("content"), str)
            ):
                raise RequestError("history elementi {role: user|assistant, content: matn} ko'rinishida bo'lishi kerak")
            if m["content"].strip():
                history.append({"role": m["role"], "content": m["content"].strip()[:HISTORY_ITEM_CHARS]})
    return question, doc_ids or None, history


def make_sources(hits: list[Hit]) -> list[dict]:
    """hits relevantlik tartibida. LLM'ga hammasi beriladi, foydalanuvchiga esa faqat eng yaxshisiga yaqinlari."""
    seen, out = set(), []
    limit = hits[0].distance + SOURCES_MARGIN
    for h in hits:
        if h.distance > limit or len(out) >= MAX_SOURCES:
            break
        key = (h.doc_id, h.page)
        if key in seen:
            continue
        seen.add(key)
        snippet = " ".join(h.text.split())
        if len(snippet) > SNIPPET_CHARS:
            snippet = snippet[: SNIPPET_CHARS - 3].rstrip() + "..."
        out.append({"doc_id": h.doc_id, "doc_name": h.doc_name, "page": h.page, "snippet": snippet})
    return out


def _is_not_found(answer: str) -> bool:
    return answer.lstrip(" \n\"'*").startswith(NOT_FOUND_TEXT[:40])


async def ask_events(request: Request, raw_body: bytes):
    try:
        if len(raw_body) > MAX_BODY_BYTES:
            raise RequestError("So'rov juda katta (ko'pi bilan 64 KB)")
        try:
            body = json.loads(raw_body)
        except ValueError:
            raise RequestError("So'rov to'g'ri JSON emas") from None
        question, doc_ids, history = parse_ask(body)

        hits = await run_in_threadpool(retrieve, question, history, doc_ids)
        if not hits:
            yield sse("token", {"text": NOT_FOUND_TEXT})
            yield sse("sources", {"sources": []})
            yield sse("done", {})
            return

        answer = ""
        async with aclosing(stream_answer(question, history, hits)) as stream:
            async for text in stream:
                answer += text
                yield sse("token", {"text": text})
                if await request.is_disconnected():
                    log.info("mijoz uzildi, LLM oqimi to'xtatildi")
                    return  # aclosing SDK oqimini ham yopadi
        if not answer.strip():
            raise RequestError(EMPTY_MESSAGE)
        yield sse("sources", {"sources": [] if _is_not_found(answer) else make_sources(hits)})
        yield sse("done", {})
    except RequestError as e:
        yield sse("error", {"message": str(e)})
    except asyncio.CancelledError:
        log.info("so'rov bekor qilindi")
        raise
    except Exception as e:
        log.error("ask/stream xatosi", exc_info=True)  # to'liq traceback faqat logda
        yield sse("error", {"message": user_message(e)})


@app.post("/ask/stream")
async def ask_stream(request: Request):
    # body oqim boshlanishidan OLDIN o'qiladi: keyin Starlette receive() ni uzilishni kuzatish uchun band qiladi
    # (chegara bilan: oshsa o'qish to'xtaydi, ask_events error voqeasini yuboradi)
    raw_body = bytearray()
    async for part in request.stream():
        raw_body += part
        if len(raw_body) > MAX_BODY_BYTES:
            break
    return StreamingResponse(ask_events(request, bytes(raw_body)), media_type="text/event-stream", headers=SSE_HEADERS)

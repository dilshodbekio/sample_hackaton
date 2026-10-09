from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

import db
import mock
from config import AI_MOCK, AI_URL, FRONTEND_ORIGIN, MAX_UPLOAD_BYTES
from sse import SSEParser, format_event

AI_UNAVAILABLE = "AI servisi bilan bog'lanib bo'lmadi. Keyinroq qayta urinib ko'ring."

http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global http_client
    db.init_db()
    http_client = httpx.AsyncClient(base_url=AI_URL, timeout=httpx.Timeout(30.0, connect=5.0))
    yield
    await http_client.aclose()


app = FastAPI(title="Attestatsiya yordamchisi — app backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_mock": AI_MOCK}


# ---------------- Hujjatlar: ai/ ga proxy (yoki mock) ----------------


def _proxy_response(resp: httpx.Response) -> Response:
    if resp.status_code == 204:
        return Response(status_code=204)
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
    )


async def _ai_request(method: str, path: str, **kwargs) -> Response:
    try:
        resp = await http_client.request(method, path, **kwargs)
    except httpx.HTTPError:
        return JSONResponse({"detail": AI_UNAVAILABLE}, status_code=502)
    return _proxy_response(resp)


@app.post("/api/documents", status_code=202)
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    if AI_MOCK:
        name = file.filename or "document.pdf"
        if not name.lower().endswith(".pdf") or not content.startswith(b"%PDF"):
            raise HTTPException(415, "Faqat PDF fayl yuklash mumkin.")
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Fayl juda katta (ko'pi bilan 20 MB).")
        return mock.create_document(name)
    files = {"file": (file.filename, content, file.content_type or "application/pdf")}
    return await _ai_request("POST", "/documents", files=files, timeout=120.0)


@app.get("/api/documents")
async def list_documents():
    if AI_MOCK:
        return mock.list_documents()
    return await _ai_request("GET", "/documents")


@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: str):
    if AI_MOCK:
        doc = mock.get_document(doc_id)
        if doc is None:
            raise HTTPException(404, "Hujjat topilmadi.")
        return doc
    return await _ai_request("GET", f"/documents/{doc_id}")


@app.delete("/api/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: str):
    if AI_MOCK:
        if not mock.delete_document(doc_id):
            raise HTTPException(404, "Hujjat topilmadi.")
        return Response(status_code=204)
    return await _ai_request("DELETE", f"/documents/{doc_id}")


# ---------------- Suhbatlar ----------------


class AskRequest(BaseModel):
    question: str
    doc_ids: list[str] | None = None


def _require_conversation(conv_id: str) -> None:
    if not db.conversation_exists(conv_id):
        raise HTTPException(404, "Suhbat topilmadi.")


@app.post("/api/conversations", status_code=201)
def create_conversation():
    return db.create_conversation()


@app.get("/api/conversations")
def list_conversations():
    return db.list_conversations()


@app.get("/api/conversations/{conv_id}/messages")
def list_messages(conv_id: str):
    _require_conversation(conv_id)
    return db.list_messages(conv_id)


async def _ai_ask_stream(payload: dict):
    """ai/ ning /ask/stream oqimini bo'laklab, buferlamasdan qaytaradi."""
    try:
        async with http_client.stream(
            "POST", "/ask/stream", json=payload, timeout=httpx.Timeout(None, connect=5.0)
        ) as resp:
            if resp.status_code != 200:
                yield format_event("error", {"message": f"AI servisi xato qaytardi (HTTP {resp.status_code})."})
                return
            async for chunk in resp.aiter_text():
                yield chunk
    except httpx.HTTPError:
        yield format_event("error", {"message": AI_UNAVAILABLE})


async def _relay(conv_id: str, payload: dict):
    """Voqealarni frontend'ga darhol uzatadi va yo'l-yo'lakay javobni yig'adi.

    Oqim oxirida: `done` → javob saqlanadi; `error` → saqlanmaydi;
    mijoz ulanishni uzsa (To'xtatish) → qisman javob `stopped=True` bilan saqlanadi.
    """
    source = mock.ask_stream(payload["question"]) if AI_MOCK else _ai_ask_stream(payload)
    parser = SSEParser()
    answer: list[str] = []
    sources: list = []
    outcome = None  # "done" | "error" | None (uzildi)
    try:
        async for chunk in source:
            for event, data in parser.feed(chunk):
                if event == "token":
                    answer.append(data.get("text", ""))
                elif event == "sources":
                    sources = data.get("sources", [])
                elif event == "done":
                    outcome = "done"
                elif event == "error":
                    outcome = "error"
            yield chunk
            if outcome:
                break
        if outcome is None:
            outcome = "error"
            yield format_event("error", {"message": "AI javobi oxirigacha kelmadi."})
    finally:
        # Saqlash await'dan oldin: bekor qilingan (cancelled) holatda await darhol uziladi.
        if outcome == "done":
            db.add_assistant_message(conv_id, "".join(answer), sources, stopped=False)
        elif outcome is None:
            db.add_assistant_message(conv_id, "".join(answer), sources, stopped=True)
        await source.aclose()  # ai/ ga ulanishni ham yopadi


@app.post("/api/conversations/{conv_id}/messages")
async def ask(conv_id: str, body: AskRequest):
    _require_conversation(conv_id)
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Savol bo'sh bo'lmasligi kerak.")

    history = db.get_history(conv_id)
    db.add_user_message(conv_id, question)
    payload = {"question": question, "doc_ids": body.doc_ids or [], "history": history}

    return StreamingResponse(
        _relay(conv_id, payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

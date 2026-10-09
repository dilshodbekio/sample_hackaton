# Attestatsiya yordamchisi (hackathon mashq loyihasi)

O'qituvchi PDF hujjat (nizom, qo'llanma) yuklaydi va ular bo'yicha savol beradi. AI faqat shu
hujjatlarga tayanib javob beradi, manbani (hujjat + bet) ko'rsatadi, javob streaming bilan
so'zma-so'z chiqadi. Maqsad: WIUT Hackathon finali (10–11 oktabr) oldidan jamoa ish jarayonini
va eng qiyin texnik qismlarni (RAG, SSE streaming) sinab ko'rish.

Minimal muvaffaqiyat: bitta PDF yuklanadi, savolga manba bilan jonli javob keladi. Qolgani bonus.

## Jamoa va papkalar

- `ai/` — Dilshodbek. RAG servisi. Python + FastAPI, port 8001. LLM va embedding: Gemini API.
- `app/` — Oybek. Backend (port 8000) + frontend (port 5173) + SQLite. Stack: backend Python + FastAPI (`httpx` bilan ai/ ga proxy va SSE uzatish, DB uchun `sqlite3`), frontend React + Vite (JavaScript) + Tailwind CSS. Vite dev proxy `/api` → `localhost:8000`.
- `docs/` — Shohijahon. Pitch va hujjatlar.

Arxitektura: frontend → app backend (/api) → ai/ servisi → LLM API.
Frontend hech qachon ai/ ni to'g'ridan-to'g'ri chaqirmaydi.

## Qat'iy qoidalar

- Faqat foydalanuvchining o'z papkasida ishla (Dilshodbek → `ai/`, Oybek → `app/`).
  Boshqa papkadagi fayllarni o'qish mumkin, o'zgartirish mumkin emas.
- `CLAUDE.md`, ildizdagi `README.md`, `.gitignore`, `docker-compose.yml` faqat ikkala dasturchi
  kelishgandan keyin o'zgartiriladi.
- Endpoint shartnomasini (pastda) o'zgartirma. O'zgartirish kerak bo'lsa, to'xta va foydalanuvchidan so'ra.
- API kalitlar faqat `.env` da. Kodga yozma, log'ga chiqarma, commit qilma. Repo PUBLIC.
- Har papkada `.env.example` bo'lsin (faqat kalit nomlari, qiymatsiz).
- Commit/push qilishdan oldin `git status` ni ko'rsat va `.env` yoki ma'lumot papkalari
  (yuklangan PDF, vektor baza, `.db`) ro'yxatda yo'qligini tekshir.

## Muhit va muloqot

- Ikkala dasturchi Windows'da Git Bash ishlatadi. Buyruqlarni Git Bash uchun ber
  (PowerShell/CMD emas). Python: `python` (ba'zan `py`), venv: `source .venv/Scripts/activate`.
- Foydalanuvchi bilan o'zbek tilida, qisqa va amaliy gaplash. Kod, identifikator va commit
  xabarlari inglizcha bo'lishi mumkin.
- Katta ishni boshlashdan oldin qisqa reja ayt. Har bosqichdan keyin ishlashini haqiqatda
  tekshir (server ishga tushir, `curl` bilan chaqir), "ishlashi kerak" deb taxmin qilma.

## Endpoint shartnomasi

Bu ikki qism o'rtasidagi yagona kelishuv. Ikkala tomon aynan shu formatga amal qiladi.

### Umumiy kelishuvlar

- Barcha JSON maydonlari `snake_case`. Vaqtlar ISO 8601 (UTC), masalan `"2026-10-09T10:00:00Z"`.
- `page` 1 dan boshlanadi (PDF'dagi birinchi bet = 1).
- `snippet` — topilgan bo'lakdan parcha, ko'pi bilan 200 belgi.
- Hujjat holati faqat uch qiymatdan biri: `processing` | `ready` | `failed`.
- Oddiy (oqim bo'lmagan) xato javoblari: tegishli HTTP kod + `{"detail": "tushunarli xabar"}`.

### A. ai/ servisi (port 8001) — faqat app backend chaqiradi

| Metod va yo'l | So'rov | Javob |
|---|---|---|
| `GET /health` | — | `200 {"status": "ok"}` |
| `POST /documents` | multipart/form-data, maydon `file` (faqat PDF, ≤ 20 MB) | `202 {"id": "doc_ab12", "name": "Nizom.pdf", "status": "processing"}` |
| `GET /documents` | — | `200 [{"id", "name", "status", "pages", "chunks", "created_at"}]` (yangisi birinchi) |
| `GET /documents/{id}` | — | `200 {"id", "name", "status", "pages", "chunks", "error", "created_at"}` |
| `DELETE /documents/{id}` | — | `204` (vektor bazadagi bo'laklar ham o'chadi) |
| `POST /ask/stream` | JSON, pastda | `200`, `text/event-stream` |

- `POST /documents` xatolari: PDF emas → `415`, juda katta → `413`.
- `GET/DELETE /documents/{id}` hujjat topilmasa → `404`.
- `pages` va `chunks` processing paytida `null` bo'lishi mumkin. `error` faqat `failed` da to'ldiriladi, aks holda `null`.
- PDF'da matn topilmasa (skaner qilingan fayl) → `status: "failed"`,
  `error: "PDF'da o'qiladigan matn topilmadi (skaner qilingan bo'lishi mumkin)"`.

`POST /ask/stream` so'rovi:

```json
{
  "question": "Oliy toifa uchun qanday talablar bor?",
  "doc_ids": ["doc_ab12"],
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

- `doc_ids` — ixtiyoriy. Bo'lmasa yoki bo'sh bo'lsa, barcha `ready` hujjatlardan qidiriladi.
- `history` — ixtiyoriy. Shu suhbatdagi oldingi xabarlar (eskisidan yangisiga, ko'pi bilan oxirgi 6 ta).
  Faqat "bu haqda batafsilroq" kabi keyingi savollarni tushunish uchun ishlatiladi; manba baribir faqat hujjatlar.

### SSE oqim formati

Javob doim HTTP `200` va `Content-Type: text/event-stream`. Har voqea bo'sh qator (`\n\n`) bilan tugaydi.
Voqealar shu tartibda keladi:

```
event: token
data: {"text": "Oliy toifa "}

event: token
data: {"text": "uchun quyidagi..."}

event: sources
data: {"sources": [{"doc_id": "doc_ab12", "doc_name": "Nizom.pdf", "page": 4, "snippet": "..."}]}

event: done
data: {}
```

- `token` — 0 yoki ko'p marta. `sources` — aniq bir marta, `done` dan oldin. `done` — oxirgi voqea.
- `sources` ichida bir xil (`doc_id`, `page`) juftligi takrorlanmaydi.
- **Javob topilmasa:** AI buni ochiq aytadi (masalan, "Yuklangan hujjatlarda bu savolga javob topilmadi."),
  `sources: []`. Hech narsa to'qib chiqarilmaydi.
- **Xato bo'lsa** (oqim boshida ham, o'rtasida ham — masalan, birorta ham `ready` hujjat yo'q,
  `doc_ids` noto'g'ri, LLM xatosi): `event: error` + `data: {"message": "tushunarli o'zbekcha xabar"}`,
  shundan keyin oqim yopiladi (`done` yuborilmaydi). Xatolar HTTP kod bilan emas, shu voqea bilan qaytadi.
- **To'xtatish:** mijoz ulanishni uzsa, server buni sezib LLM oqimini ham to'xtatadi.

### B. app backend (port 8000) — frontend chaqiradi, hammasi `/api` bilan

| Metod va yo'l | Nima qiladi |
|---|---|
| `POST /api/documents`, `GET /api/documents`, `GET /api/documents/{id}`, `DELETE /api/documents/{id}` | ai/ ga proxy. So'rov, javob va HTTP kodlar ai/ dagi bilan bir xil |
| `POST /api/conversations` | Yangi suhbat → `201 {"id", "title": "Yangi suhbat", "created_at"}` |
| `GET /api/conversations` | `[{"id", "title", "created_at"}]`, yangisi birinchi |
| `GET /api/conversations/{id}/messages` | `[{"id", "role": "user"\|"assistant", "content", "sources", "stopped", "created_at"}]`, eskisi birinchi |
| `POST /api/conversations/{id}/messages` | Pastda |

`POST /api/conversations/{id}/messages`, so'rov: `{"question": "...", "doc_ids": [...]}` (`doc_ids` ixtiyoriy).

1. Foydalanuvchi savolini darhol DB'ga saqlaydi. Bu suhbatdagi birinchi savol bo'lsa,
   `title` = savolning dastlabki 40 belgisi.
2. Shu suhbatdagi oldingi xabarlardan `history` yig'adi va ai/ ning `/ask/stream` ini chaqiradi.
3. ai/ dan kelgan voqealarni (`token`, `sources`, `done`, `error`) **xuddi shu formatda,
   buferlamasdan** frontend'ga uzatadi.
4. Oqim tugagach, to'liq javob va manbalarni assistant xabari sifatida saqlaydi.
   - Foydalanuvchi "To'xtatish" bossa: shu paytgacha kelgan qisman javob `stopped: true` bilan saqlanadi.
   - `error` kelsa: assistant xabari saqlanmaydi.

Suhbat topilmasa → `404`.

### Mock rejim (app backend)

`AI_MOCK=true` bo'lsa ai/ chaqirilmaydi, backend o'zi soxta javob beradi:

- Savol: soxta matn so'zma-so'z, har 50 ms da bitta `token`, keyin soxta `sources`
  (`{"doc_id": "doc_mock", "doc_name": "Namuna.pdf", "page": 1, "snippet": "..."}`) va `done`.
- Savolda `test-topilmadi` bo'lsa: "javob topilmadi" matni, `sources: []`.
- Savolda `test-xato` bo'lsa: bir nechta `token` dan keyin `error` voqeasi.
- Yuklash: 5 soniya `processing`, keyin `ready` (`pages: 10`, `chunks: 25`).

## .env kalitlari

- `ai/.env`: `GEMINI_API_KEY`, `DATA_DIR` (yuklangan PDF, vektor baza, hujjat holatlari shu yerda; standart `./data`)
- `app/.env`: `AI_MOCK` (`true`/`false`), `AI_URL` (standart `http://localhost:8001`), `FRONTEND_ORIGIN` (CORS uchun)

## ai/ uchun eslatmalar (Dilshodbek)

- Tuzilma: ingest (o'qish + bo'laklash), retrieve (qidiruv), generate (prompt + LLM) alohida modullarda.
  Ertaga hackathonda mavzu o'zgarsa, faqat prompt va ma'lumot almashadi.
- Har bo'lakda `doc_id`, `doc_name`, `page` metadata sifatida saqlanadi. Bet raqami keyin tiklanmaydi.
- Embedding uchun ko'p tilli model ishlat (Chroma'ning standart inglizcha modeli emas).
- Hujjat holatlari diskda saqlanadi (`DATA_DIR`), xotirada emas. Servis qayta ishga tushsa ham yo'qolmasin.
- Topilgan bo'laklar o'xshashlik chegarasidan o'tmasa, LLM chaqirilmaydi va "topilmadi" javobi qaytadi.
- Sinov: `curl -N -X POST localhost:8001/ask/stream -H "Content-Type: application/json" -d '{"question":"..."}'`.

## app/ uchun eslatmalar (Oybek)

- Frontend oqimni `fetch` + `ReadableStream` bilan o'qiydi (`EventSource` faqat GET qiladi, to'g'ri kelmaydi).
  Kelgan matnni bufer'da yig'ib, `\n\n` bo'yicha voqealarga ajrat: bitta voqea ikki bo'lakka bo'linib kelishi mumkin.
- "To'xtatish" → `AbortController`. Backend ulanish uzilganini sezib, ai/ ga so'rovni ham uzadi.
- Javob kelayotganda yuborish tugmasi bloklanadi. Server o'chiq yoki `error` kelsa, tushunarli xabar ko'rsatiladi.
- Hujjat holati: `processing` bo'lsa har 2 soniyada `GET /api/documents/{id}`, `ready`/`failed` da to'xtaydi.
- Backend CORS'da `FRONTEND_ORIGIN` ga ruxsat beradi.

## Git

- Ishdan oldin `git pull`. Har 30–60 daqiqada kichik commit + push.
- Commit xabari papka nomi bilan boshlanadi: `ai: ...`, `app: ...`, `docs: ...`.
- `git push` rad etilsa: avval `git pull`, keyin yana `git push`. Majburiy push (`--force`) qilinmaydi.

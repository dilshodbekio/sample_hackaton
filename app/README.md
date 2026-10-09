# app/ — backend + frontend (Oybek)

- `backend/` — FastAPI, port 8000. SQLite (`backend/app.db`, commit qilinmaydi), ai/ ga proxy va SSE uzatish, mock rejim.
- `frontend/` — React + Vite + Tailwind, port 5173. `/api` so'rovlari Vite proxy orqali `localhost:8000` ga boradi.
- `.env` — `app/` ichida (namuna: `.env.example`).

## Birinchi marta (Git Bash)

```bash
cd app
cp .env.example .env        # AI_MOCK=true, AI_URL=http://localhost:8001, FRONTEND_ORIGIN=http://localhost:5173

cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt

cd ../frontend
npm install
```

## Ishga tushirish (ikkita terminal)

```bash
# 1-terminal
cd app/backend && source .venv/Scripts/activate && uvicorn main:app --reload --port 8000

# 2-terminal
cd app/frontend && npm run dev
```

Brauzer: http://localhost:5173

## Mock rejim (`AI_MOCK=true`)

ai/ chaqirilmaydi. Savolga soxta javob so'zma-so'z keladi (har 50 ms), keyin `Namuna.pdf, 1-bet` manbasi.
Savolda `test-topilmadi` bo'lsa — "javob topilmadi", `test-xato` bo'lsa — bir nechta so'zdan keyin xato.
Yuklangan PDF 5 soniya `processing`, keyin `ready` (mock hujjatlar xotirada, backend qayta ishga tushsa yo'qoladi).

## Haqiqiy ai/ ga ulash

`app/.env` da `AI_MOCK=false`, `AI_URL=http://localhost:8001` (yoki Dilshodbekning IP manzili), backend'ni qayta ishga tushiring.

## Tez tekshirish (curl)

```bash
curl -s -X POST localhost:8000/api/conversations
curl -N -X POST localhost:8000/api/conversations/<id>/messages -H "Content-Type: application/json" -d '{"question":"Oliy toifa uchun qanday talablar bor?"}'
```

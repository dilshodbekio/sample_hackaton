import json
import sqlite3
import uuid
from datetime import datetime, timezone

from config import DB_PATH, HISTORY_LIMIT

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources_json TEXT NOT NULL DEFAULT '[]',
    stopped INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);
"""

DEFAULT_TITLE = "Yangi suhbat"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def create_conversation() -> dict:
    conv = {"id": new_id("conv"), "title": DEFAULT_TITLE, "created_at": now_iso()}
    with connect() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at) VALUES (?, ?, ?)",
            (conv["id"], conv["title"], conv["created_at"]),
        )
    return conv


def list_conversations() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at FROM conversations ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def conversation_exists(conv_id: str) -> bool:
    with connect() as conn:
        row = conn.execute("SELECT 1 FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    return row is not None


def _message_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "sources": json.loads(row["sources_json"]),
        "stopped": bool(row["stopped"]),
        "created_at": row["created_at"],
    }


def list_messages(conv_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conv_id,),
        ).fetchall()
    return [_message_from_row(r) for r in rows]


def get_history(conv_id: str) -> list[dict]:
    """Oxirgi HISTORY_LIMIT ta xabar, eskisidan yangisiga (ai/ uchun `history`)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (conv_id, HISTORY_LIMIT),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def add_user_message(conv_id: str, question: str) -> None:
    """Savolni saqlaydi; suhbatdagi birinchi savol bo'lsa sarlavhani ham qo'yadi."""
    with connect() as conn:
        is_first = conn.execute(
            "SELECT 1 FROM messages WHERE conversation_id = ? AND role = 'user' LIMIT 1",
            (conv_id,),
        ).fetchone() is None
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, created_at) "
            "VALUES (?, ?, 'user', ?, ?)",
            (new_id("msg"), conv_id, question, now_iso()),
        )
        if is_first:
            conn.execute(
                "UPDATE conversations SET title = ? WHERE id = ?",
                (question[:40], conv_id),
            )


def add_assistant_message(conv_id: str, content: str, sources: list, stopped: bool) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, sources_json, stopped, created_at) "
            "VALUES (?, ?, 'assistant', ?, ?, ?, ?)",
            (new_id("msg"), conv_id, content, json.dumps(sources, ensure_ascii=False), int(stopped), now_iso()),
        )

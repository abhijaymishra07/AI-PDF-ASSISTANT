import json
import uuid

from backend.app.db.database import get_conn


def create_session(user_id: int | None, title: str = "New chat") -> str:
    session_id = str(uuid.uuid4())[:12]
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_sessions (id, user_id, title) VALUES (?, ?, ?)",
            (session_id, user_id, title),
        )
    return session_id


def save_message(
    session_id: str,
    role: str,
    content: str,
    user_id: int | None = None,
    doc_ids: list[str] | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO chat_messages (session_id, user_id, role, content, doc_ids)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, user_id, role, content, json.dumps(doc_ids) if doc_ids else None),
        )


def list_sessions(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT s.id, s.title, s.created_at,
                      (SELECT content FROM chat_messages m
                       WHERE m.session_id = s.id ORDER BY m.id DESC LIMIT 1) AS last_message
               FROM chat_sessions s
               WHERE s.user_id = ?
               ORDER BY s.created_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_messages(session_id: str, user_id: int) -> list[dict]:
    with get_conn() as conn:
        session = conn.execute(
            "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not session:
            return []
        rows = conn.execute(
            """SELECT role, content, doc_ids, created_at
               FROM chat_messages WHERE session_id = ? ORDER BY id""",
            (session_id,),
        ).fetchall()
    result = []
    for r in rows:
        item = dict(r)
        if item.get("doc_ids"):
            item["doc_ids"] = json.loads(item["doc_ids"])
        result.append(item)
    return result

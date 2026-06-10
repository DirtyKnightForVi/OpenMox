"""
SQLite-backed persistence for projects, sessions, and messages.

Uses aiosqlite for async access.  Schema is created automatically on first
call to `init_db()`.

Tables:
  projects  — {id, name, full_path, display_name, created_at}
  sessions  — {id, project_id, session_key, created_at}  (= Window)
  messages  — {id, session_id, speaker_type, speaker_id, content, timestamp}
  memory_entries — {id, agent_id, project_id, scope, type, content, source, importance, pinned, deprecated, created_at}
  dream_snapshots — {id, agent_id, project_id, created_at, entry_count_before, entry_count_after, rolled_back}
"""

import json
import time
from pathlib import Path
from typing import Optional

import aiosqlite

from .logging import get_logger

log = get_logger(__name__)

# ── Schema ─────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    full_path   TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    session_key TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
    speaker_type TEXT NOT NULL DEFAULT 'human' CHECK(speaker_type IN ('human', 'agent')),
    speaker_id  TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL DEFAULT '',
    timestamp   REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_key ON sessions(session_key);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
-- Composite index for reflection queries: "find agent's recent N messages"
CREATE INDEX IF NOT EXISTS idx_messages_speaker_time ON messages(speaker_type, speaker_id, timestamp DESC);

-- Memory: White-box memory entries (one per extracted fact/decision/preference)
CREATE TABLE IF NOT EXISTS memory_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id    TEXT NOT NULL,
    project_id  TEXT NOT NULL DEFAULT '',
    scope       TEXT NOT NULL DEFAULT 'private' CHECK(scope IN ('private', 'shared')),
    type        TEXT NOT NULL DEFAULT 'fact' CHECK(type IN ('fact', 'decision', 'preference', 'context')),
    content     TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT '',
    importance  REAL NOT NULL DEFAULT 0.5,
    pinned      INTEGER NOT NULL DEFAULT 0,
    deprecated  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_memory_agent ON memory_entries(agent_id, deprecated);
CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_entries(project_id, scope);

-- Dream snapshots (one per dream cycle per agent)
CREATE TABLE IF NOT EXISTS dream_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL,
    project_id      TEXT NOT NULL DEFAULT '',
    entry_count_before INTEGER NOT NULL DEFAULT 0,
    entry_count_after  INTEGER NOT NULL DEFAULT 0,
    rolled_back     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_snapshots_agent ON dream_snapshots(agent_id, rolled_back);
"""

# ── Connection ─────────────────────────────────────────

_db: Optional[aiosqlite.Connection] = None


async def get_db(db_path: str = "data/openmox.db") -> aiosqlite.Connection:
    """Return a singleton database connection, creating it on first call."""
    global _db
    if _db is None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _db = await aiosqlite.connect(db_path)
        _db.row_factory = aiosqlite.Row
        await _db.executescript(SCHEMA)
        await _db.commit()
        log.info("SQLite opened: %s", db_path)
    return _db


async def close_db() -> None:
    """Close the database connection if open."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        log.info("SQLite closed")


# ── Projects ───────────────────────────────────────────


async def list_projects() -> list[dict]:
    """Return all projects."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM projects ORDER BY created_at DESC")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_project_by_name(name: str) -> Optional[dict]:
    """Find a project by name."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM projects WHERE name = ?", (name,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_project(name: str, full_path: str, display_name: str = "") -> dict:
    """Create a project. Returns the created row as a dict."""
    db = await get_db()
    cursor = await db.execute(
        "INSERT OR IGNORE INTO projects (name, full_path, display_name) VALUES (?, ?, ?)",
        (name, full_path, display_name or name),
    )
    await db.commit()
    # Fetch the row (whether newly inserted or existing)
    return await get_project_by_name(name) or {}


async def delete_project(name: str) -> bool:
    """Delete a project by name. Returns True if found and deleted."""
    db = await get_db()
    cursor = await db.execute("DELETE FROM projects WHERE name = ?", (name,))
    await db.commit()
    return cursor.rowcount > 0


# ── Sessions ───────────────────────────────────────────


async def ensure_session(session_key: str, project_name: str = "") -> dict:
    """Get or create a session by its key. Returns {id, session_key, ...}."""
    db = await get_db()

    # Try find existing
    cursor = await db.execute(
        "SELECT * FROM sessions WHERE session_key = ?", (session_key,)
    )
    row = await cursor.fetchone()
    if row:
        return dict(row)

    # Find project id if project_name provided
    project_id = None
    if project_name:
        proj = await get_project_by_name(project_name)
        if proj:
            project_id = proj["id"]

    cursor = await db.execute(
        "INSERT INTO sessions (project_id, session_key) VALUES (?, ?)",
        (project_id, session_key),
    )
    await db.commit()
    return {"id": cursor.lastrowid, "session_key": session_key, "project_id": project_id}


# ── Messages ───────────────────────────────────────────


async def get_window_context(
    session_key: str,
    limit: int = 20,
) -> list[dict]:
    """Return the last N messages in a session (window), oldest-first.

    Used for context seeding — every agent woken up in this window sees
    the recent conversation timeline.
    """
    db = await get_db()
    # Subquery: get last N message ids for this session, then fetch in ASC order
    cursor = await db.execute(
        """
        SELECT * FROM (
            SELECT * FROM messages
            JOIN sessions ON messages.session_id = sessions.id
            WHERE sessions.session_key = ?
            ORDER BY messages.timestamp DESC
            LIMIT ?
        ) ORDER BY timestamp ASC
        """,
        (session_key, limit),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_messages(session_key: str) -> list[dict]:
    """Return all message history for a session."""
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT m.* FROM messages m
        JOIN sessions s ON m.session_id = s.id
        WHERE s.session_key = ?
        ORDER BY m.timestamp ASC
        """,
        (session_key,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def append_message(
    session_key: str,
    content: str,
    *,
    speaker_type: str = "human",
    speaker_id: str = "",
) -> None:
    """Append a single message to a session's (window's) timeline.

    Args:
        session_key: The session/window identifier.
        content: The message text.
        speaker_type: 'human' or 'agent'.
        speaker_id: The agent_id if speaker_type='agent', or user identifier.
    """
    db = await get_db()
    session = await ensure_session(session_key)

    await db.execute(
        "INSERT INTO messages (session_id, speaker_type, speaker_id, content, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        (session["id"], speaker_type, speaker_id, content, time.time()),
    )
    await db.commit()

    # Trim to last 500 messages per session
    await db.execute(
        """
        DELETE FROM messages WHERE id IN (
            SELECT id FROM messages WHERE session_id = ?
            ORDER BY timestamp ASC LIMIT -1 OFFSET 500
        )
        """,
        (session["id"],),
    )
    await db.commit()

    # Global retention: keep last 1,000 messages across all sessions
    await db.execute(
        """
        DELETE FROM messages WHERE id IN (
            SELECT id FROM messages
            ORDER BY timestamp ASC LIMIT -1 OFFSET 1000
        )
        """,
    )
    await db.commit()


# ── Memory ─────────────────────────────────────────────


async def insert_memory(
    agent_id: str,
    project_id: str,
    *,
    scope: str = "private",
    type: str = "fact",
    content: str,
    source: str = "",
    importance: float = 0.5,
) -> int:
    """Insert a single memory entry. Returns the new row id."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO memory_entries
           (agent_id, project_id, scope, type, content, source, importance)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (agent_id, project_id, scope, type, content, source, importance),
    )
    await db.commit()
    return cursor.lastrowid or 0


async def insert_memory_batch(entries: list[dict]) -> int:
    """Insert multiple memory entries in one transaction. Returns count."""
    if not entries:
        return 0
    db = await get_db()
    count = 0
    for e in entries:
        await db.execute(
            """INSERT INTO memory_entries
               (agent_id, project_id, scope, type, content, source, importance)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                e.get("agent_id", ""),
                e.get("project_id", ""),
                e.get("scope", "private"),
                e.get("type", "fact"),
                e.get("content", ""),
                e.get("source", ""),
                e.get("importance", 0.5),
            ),
        )
        count += 1
    await db.commit()
    return count


async def list_memory(
    agent_id: str | None = None,
    *,
    scope: str | None = None,
    include_deprecated: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List memory entries, newest first.

    If agent_id is None, returns memories across all agents
    (used for shared memory queries).
    """
    db = await get_db()
    clauses: list[str] = []
    params: list = []
    if agent_id is not None:
        clauses.append("agent_id = ?")
        params.append(agent_id)
    if scope is not None:
        clauses.append("scope = ?")
        params.append(scope)
    if not include_deprecated:
        clauses.append("deprecated = 0")
    where = " AND ".join(clauses) if clauses else "1=1"
    cursor = await db.execute(
        f"SELECT * FROM memory_entries WHERE {where} "
        "ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_memory(memory_id: int, **updates) -> dict | None:
    """Update fields of a memory entry. Returns the updated row or None."""
    allowed = {"content", "importance", "pinned", "deprecated", "scope", "type"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return None
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [memory_id]
    db = await get_db()
    await db.execute(
        f"UPDATE memory_entries SET {set_clause} WHERE id = ?",
        values,
    )
    await db.commit()
    cursor = await db.execute("SELECT * FROM memory_entries WHERE id = ?", (memory_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def deprecate_memory_batch(ids: list[int]) -> int:
    """Mark a batch of memory entries as deprecated. Returns count."""
    if not ids:
        return 0
    db = await get_db()
    placeholders = ",".join("?" for _ in ids)
    cursor = await db.execute(
        f"UPDATE memory_entries SET deprecated = 1 WHERE id IN ({placeholders})",
        ids,
    )
    await db.commit()
    return cursor.rowcount


async def create_snapshot(
    agent_id: str,
    project_id: str = "",
    entry_count_before: int = 0,
) -> int:
    """Create a dream snapshot. Returns the snapshot id."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO dream_snapshots (agent_id, project_id, entry_count_before)
           VALUES (?, ?, ?)""",
        (agent_id, project_id, entry_count_before),
    )
    await db.commit()
    return cursor.lastrowid or 0


async def finalize_snapshot(snapshot_id: int, entry_count_after: int) -> None:
    """Mark a snapshot as complete with final entry count."""
    db = await get_db()
    await db.execute(
        "UPDATE dream_snapshots SET entry_count_after = ? WHERE id = ?",
        (entry_count_after, snapshot_id),
    )
    await db.commit()


async def get_last_snapshot(agent_id: str) -> dict | None:
    """Return the most recent non-rolled-back snapshot for an agent."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM dream_snapshots
           WHERE agent_id = ? AND rolled_back = 0
           ORDER BY created_at DESC LIMIT 1""",
        (agent_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def rollback_snapshot(snapshot_id: int) -> bool:
    """Mark a snapshot as rolled back. Returns True on success."""
    db = await get_db()
    cursor = await db.execute(
        "UPDATE dream_snapshots SET rolled_back = 1 WHERE id = ?",
        (snapshot_id,),
    )
    await db.commit()
    return cursor.rowcount > 0

"""
Dream/Reflect engine — shared logic for quick reflection, shendu (睡前慎独),
and manual memory consolidation.

All three trigger types invoke reflect() with different scopes and prompts.
The engine:
  1. Pulls relevant messages from the messages table (with composite index)
  2. Runs rule-based extraction as structured context
  3. Calls LLM (cheapest model) to extract semantic memories
  4. Writes to memory_entries (with snapshot/deprecate for shendu)
"""

from __future__ import annotations

from typing import Literal

from ..core.logging import get_logger

log = get_logger(__name__)

# Upper limit on total messages pulled for shendu
_MAX_TOTAL_MESSAGES = 200

# ── Default prompts ──────────────────────────────────

DEFAULT_QUICK_PROMPT = """你正在进行一次简短的自我反思。以下是你在最近一段工作中的对话记录。

请从中提取：
1. 你完成了什么具体任务？
2. 是否有需要跟进的事项？
3. 是否从中学到了什么（新知识、模式、经验）？

用简洁的中文回答，每条一行。如果没有值得记住的内容，回答 "(empty)"。"""

DEFAULT_SHENDU_PROMPT = """夜深了，请回顾你今天的工作。

请整理以下内容：
1. 今天做出的关键决策（最多 3 个）
2. 遗留问题和未完成事项
3. 明天优先要做的事（最多 3 件）
4. 今天学到的新知识或发现的模式

用结构化格式回答，合并重复信息。

## 如果你是 momo（项目协调者）
请额外检查看板和团队成员的工作记录。如果发现跨 Agent 的共识或决策尚未
写入共同记忆，请在输出中包含 scope=shared 的条目（使用 WriteSharedMemory 工具）。
格式: "[shared] 项目决定: ..." """


# ═══════════════════════════════════════════════════════

async def reflect(
    *,
    agent_id: str,
    project_id: str = "",
    scope: Literal["quick", "shendu", "manual"] = "quick",
    shendu_prompt: str | None = None,
    window_id: str = "",
) -> dict:
    """Run one reflection cycle for an agent.

    Returns {"entries_written": N, "snapshot_id": S | None, "scope": scope}.
    """
    # ── 1. Pull messages ───────────────────────────
    if scope == "shendu":
        messages = await _get_shendu_messages(agent_id, project_id)
    else:
        # quick / manual: read from Redis AgentState (no SQL needed)
        messages = await _get_quick_reflect_context(agent_id, window_id)

    if not messages:
        log.info("reflect(%s, %s): no messages to reflect on", agent_id, scope)
        return {"entries_written": 0, "snapshot_id": None, "scope": scope}

    # ── 2. Rule-based extraction as structured context ──
    structured_lines = _rule_extract_context(messages)

    # ── 3. Build prompt ────────────────────────────
    if scope == "quick" or scope == "manual":
        prompt = DEFAULT_QUICK_PROMPT
    else:
        prompt = shendu_prompt or _load_shendu_prompt(agent_id)

    llm_input = _format_messages(messages)
    if structured_lines:
        llm_input += "\n\n## 结构化摘要\n" + "\n".join(structured_lines)

    # ── 4. Call LLM ────────────────────────────────
    result_text = await _call_llm(prompt, llm_input)
    if not result_text or result_text.strip() == "(empty)":
        log.info("reflect(%s, %s): LLM returned empty", agent_id, scope)
        return {"entries_written": 0, "snapshot_id": None, "scope": scope}

    # ── 5. Write to memory_entries ─────────────────
    from ..core import store as mem_store

    entry_type = "reflection" if scope == "quick" else "shendu"
    importance = 0.4 if scope == "quick" else 0.8

    entries = _parse_reflection_result(result_text, agent_id, project_id, entry_type, importance)

    snapshot_id = None
    if scope == "shendu":
        # Snapshot: deprecate old entries, write new ones, create snapshot
        old = await mem_store.list_memory(agent_id, limit=500)
        old_ids = [r["id"] for r in old]
        count_before = len(old_ids)
        snapshot_id = await mem_store.create_snapshot(agent_id, project_id, count_before)
        if old_ids:
            await mem_store.deprecate_memory_batch(old_ids)
        await mem_store.insert_memory_batch(entries)
        await mem_store.finalize_snapshot(snapshot_id, len(entries))
        # ── Clean consumed messages (慎独后清旧对话) ──
        try:
            from ..core.store import get_db
            snap = await mem_store.get_last_snapshot(agent_id)
            if snap and snap.get("created_at"):
                db = await get_db()
                await db.execute(
                    "DELETE FROM messages WHERE timestamp < ?",
                    (snap["created_at"],),
                )
                await db.commit()
                log.info("reflect(%s, shendu): cleaned messages before %s", agent_id, snap["created_at"])
        except Exception as e:
            log.warning("reflect(%s, shendu): cleanup failed: %s", agent_id, e)
    else:
        # Quick: just append
        await mem_store.insert_memory_batch(entries)

    log.info(
        "reflect(%s, %s): wrote %d entries (snapshot=%s)",
        agent_id, scope, len(entries), snapshot_id,
    )
    return {"entries_written": len(entries), "snapshot_id": snapshot_id, "scope": scope}


# ═══════════════════════════════════════════════════════
# Message pulling
# ═══════════════════════════════════════════════════════

async def _get_quick_reflect_context(agent_id: str, window_id: str) -> list[dict]:
    """Pull conversation context for quick reflection.

    Reads from the window stream replay log (the shared timeline)
    instead of the old session_store. This gives a complete view of
    what happened in the window, including human messages and all
    agent replies.

    Falls back to empty list if the window stream is unavailable.
    """
    try:
        from main import app as _app
        message_bus = getattr(_app.state, 'message_bus', None)
        if message_bus is None:
            return []
        key = f"window:{window_id}:events"
        entries = await message_bus.log_read(key, max_count=50)
        rows: list[dict] = []
        for _entry_id, payload in entries:
            t = payload.get("type", "")
            if t == "human_message":
                rows.append({
                    "speaker_type": "human",
                    "speaker_id": payload.get("speaker_id", "user"),
                    "content": payload.get("content", ""),
                })
            elif t in ("TEXT_BLOCK_END",) and payload.get("text"):
                rows.append({
                    "speaker_type": "agent",
                    "speaker_id": payload.get("_agent_id", ""),
                    "content": payload.get("text", ""),
                })
        return rows
    except Exception:
        return []


async def _get_shendu_messages(agent_id: str, project_id: str) -> list[dict]:
    """Pull all messages since last shendu snapshot for this agent, cross-window.

    Uses SQLite messages table (not Redis) because AgentState.context is
    lossy — old details are compressed into state.summary. Shendu needs
    the full conversation record.
    """
    from ..core.store import get_db

    db = await get_db()
    cursor = await db.execute(
        """SELECT created_at FROM dream_snapshots
           WHERE agent_id = ? AND rolled_back = 0
           ORDER BY created_at DESC LIMIT 1""",
        (agent_id,),
    )
    snap_row = await cursor.fetchone()
    since_ts = snap_row["created_at"] if snap_row else 0

    if since_ts == 0:
        cursor = await db.execute(
            """SELECT speaker_type, speaker_id, content, timestamp
               FROM messages ORDER BY timestamp ASC LIMIT ?""",
            (500,),
        )
    else:
        cursor = await db.execute(
            """SELECT speaker_type, speaker_id, content, timestamp
               FROM messages WHERE timestamp >= ? ORDER BY timestamp ASC LIMIT ?""",
            (since_ts, _MAX_TOTAL_MESSAGES),
        )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════
# Rule-based extraction (lightweight, no LLM)
# ═══════════════════════════════════════════════════════

def _rule_extract_context(messages: list[dict]) -> list[str]:
    """Extract structured context lines from raw messages.

    This mirrors MemoryCaptureMiddleware logic but operates on the dict-
    shaped rows from the messages table instead of AgentScope block objects.
    """
    lines: list[str] = []
    for m in messages:
        speaker = m.get("speaker_id", "?")
        content = m.get("content", "")
        if m.get("speaker_type") == "agent":
            # Agent message — summarize
            lines.append(f"[{speaker}]: {content[:200]}")
        else:
            lines.append(f"[{speaker}]: {content[:200]}")
    return lines


# ═══════════════════════════════════════════════════════
# LLM call
# ═══════════════════════════════════════════════════════

async def _call_llm(system_prompt: str, user_content: str) -> str:
    """Call the model for extraction using runtime credentials.

    Uses get_settings() for API key (environment variables, always current)
    rather than the model singleton's credential (cached at startup).
    """
    from ..core.settings import get_settings
    import httpx

    s = get_settings()
    url = f"{s.deepseek_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {s.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": s.deepseek_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
        "max_tokens": 1000,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════

def _format_messages(messages: list[dict]) -> str:
    """Format message rows into readable text for the LLM."""
    lines: list[str] = []
    for m in messages:
        speaker = m.get("speaker_id", "?")
        speaker_type = m.get("speaker_type", "?")
        content = m.get("content", "")
        label = f"[{speaker}]" if speaker_type == "agent" else "[用户]"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def _load_shendu_prompt(agent_id: str, project_root: str = ".") -> str:
    """Load the shendu (慎独) prompt from agent.yaml, falling back to default."""
    from ..dao import ConfigDAO
    dao = ConfigDAO(project_root)
    cfg = dao.get_agent(agent_id)
    if cfg and cfg.shendu_prompt:
        return cfg.shendu_prompt
    return DEFAULT_SHENDU_PROMPT


def _parse_reflection_result(
    text: str,
    agent_id: str,
    project_id: str,
    entry_type: str,
    importance: float,
) -> list[dict]:
    """Split LLM output into individual memory entries.

    Each non-empty line becomes one entry. Blank lines are skipped.
    Lines longer than 500 chars are truncated.
    """
    entries: list[dict] = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        entries.append({
            "agent_id": agent_id,
            "project_id": project_id,
            "scope": "private",
            "type": entry_type,
            "content": line[:_MAX_CONTENT_LEN],
            "source": f"reflect:{entry_type}",
            "importance": importance,
        })
    return entries


_MAX_CONTENT_LEN = 500

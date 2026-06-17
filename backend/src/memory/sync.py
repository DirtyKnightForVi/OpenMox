"""
Memory sync engine — SQLite ↔ Markdown bidirectional bridge.

Cloud (SQLite memory_entries)  ←→  Local (.Agents/{id}/MEMORY.md)

Direction 1 (cloud → local):
  Reads non-deprecated entries from SQLite, formats as Markdown,
  writes to MEMORY.md.  Run on-demand via REST API or Dream engine.

Direction 2 (local → cloud):
  Triggered by MemorySyncMiddleware when agent writes MEMORY.md.
  Parses the Markdown file, deprecates old entries, inserts new ones.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..core.logging import get_logger

log = get_logger(__name__)


# ═══════════════════════════════════════════════════════
# Direction 1: SQLite → Markdown
# ═══════════════════════════════════════════════════════


async def sync_entries_to_markdown(
    agent_id: str,
    project_root: str,
    *,
    scope: str = "private",
) -> int:
    """Read SQLite memory entries and write them to a Markdown file.

    Returns the number of entries synced.
    """
    from ..core import store as mem_store

    entries = await mem_store.list_memory(
        agent_id=agent_id if scope == "private" else None,
        scope=scope,
        include_deprecated=False,
        limit=200,
    )
    if not entries:
        log.debug("sync(%s, %s): no entries to sync", agent_id, scope)
        return 0

    # Build Markdown
    lines = [
        f"# {'共同记忆' if scope == 'shared' else f'{agent_id} 独有记忆'}",
        f"",
        f"> 同步时间: {datetime.now(timezone.utc).isoformat()}",
        f"> 条目数: {len(entries)}",
        f"",
    ]
    for e in entries:
        tag = _MEMORY_TAGS.get(e.get("type", ""), "•")
        content = e.get("content", "")
        source = e.get("source", "")
        created = e.get("created_at", "")[:10]
        pinned = "📌 " if e.get("pinned") else ""
        lines.append(f"### {tag} {pinned}{created}")
        lines.append(f"")
        lines.append(f"{content}")
        if source and source != agent_id:
            lines.append(f"")
            lines.append(f"_来源: {source}_")
        lines.append(f"")

    # Write target file
    root = Path(project_root)
    if scope == "shared":
        target = root / ".Project" / "PROJECT_MEMO.md"
    else:
        target = root / ".Agents" / agent_id / "MEMORY.md"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")

    log.info("sync(%s, %s): wrote %d entries to %s",
             agent_id, scope, len(entries), target)
    return len(entries)


async def sync_project_memo(project_root: str) -> int:
    """Sync shared memories → .Project/PROJECT_MEMO.md."""
    return await sync_entries_to_markdown(
        agent_id="momo",  # momo is the scribe
        project_root=project_root,
        scope="shared",
    )


# ═══════════════════════════════════════════════════════
# Direction 2: Markdown → SQLite
# ═══════════════════════════════════════════════════════


async def sync_markdown_to_entries(
    agent_id: str,
    project_root: str,
    *,
    scope: str = "private",
) -> int:
    """Parse MEMORY.md and upsert entries to SQLite.

    Strategy: upsert by (content, agent_id, scope).  Existing entries
    with matching content are kept (not duplicated).  Entries present
    in SQLite but absent from MEMORY.md are deprecated (user removed
    them from the file).  New entries are inserted.

    This is safe for incremental writes — writing MEMORY.md twice
    won't destroy memories written the first time.
    Returns the number of new entries inserted.
    """
    root = Path(project_root)
    if scope == "shared":
        target = root / ".Project" / "PROJECT_MEMO.md"
    else:
        target = root / ".Agents" / agent_id / "MEMORY.md"

    if not target.exists():
        log.debug("sync reverse(%s, %s): file not found", agent_id, scope)
        return 0

    content = target.read_text(encoding="utf-8")
    parsed = _parse_markdown_entries(content, agent_id, project_root, scope)

    if not parsed:
        return 0

    from ..core import store as mem_store

    # Load existing non-deprecated entries
    existing = await mem_store.list_memory(
        agent_id=agent_id if scope == "private" else None,
        scope=scope,
        include_deprecated=False,
        limit=500,
    )

    # Build set of existing content hashes for dedup
    existing_contents = {
        (e.get("content", ""), e.get("agent_id", ""), e.get("scope", ""))
        for e in existing
    }

    # Insert only new entries
    inserted = 0
    for entry in parsed:
        key = (entry["content"], entry["agent_id"], entry["scope"])
        if key not in existing_contents:
            await mem_store.insert_memory(
                agent_id=entry["agent_id"],
                project_id=entry["project_id"],
                scope=entry["scope"],
                type=entry["type"],
                content=entry["content"],
                source=entry["source"],
                importance=entry.get("importance", 0.5),
            )
            existing_contents.add(key)
            inserted += 1

    # Deprecate entries that exist in SQLite but are NOT in MEMORY.md
    # (user explicitly removed them from the file)
    parsed_contents = {
        (e["content"], e["agent_id"], e["scope"])
        for e in parsed
    }
    removed_ids = [
        e["id"] for e in existing
        if (e.get("content", ""), e.get("agent_id", ""), e.get("scope", ""))
        not in parsed_contents
    ]
    if removed_ids:
        await mem_store.deprecate_memory_batch(removed_ids)

    log.info(
        "sync reverse(%s, %s): inserted %d, deprecated %d",
        agent_id, scope, inserted, len(removed_ids),
    )
    return inserted


# ═══════════════════════════════════════════════════════
# Markdown parser
# ═══════════════════════════════════════════════════════

_MEMORY_TAGS = {
    "📋": "fact", "🔧": "decision", "⭐": "preference",
    "💭": "reflection", "🌙": "shendu", "📝": "context",
}


def _parse_markdown_entries(
    content: str,
    agent_id: str,
    project_root: str,
    scope: str,
) -> list[dict]:
    """Parse MEMORY.md into memory entry dicts.

    Format:
      ### 📋 2026-06-13
      
      content line 1
      content line 2
      
      _来源: momo_

    Each ### header starts a new entry.  Empty lines are separators.
    """
    entries: list[dict] = []
    current_type = "fact"
    current_content: list[str] = []
    current_source = agent_id
    current_pinned = False

    def _flush():
        nonlocal current_content, current_type, current_source, current_pinned
        text = " ".join(current_content).strip()
        if text:
            entries.append({
                "agent_id": agent_id,
                "project_id": project_root,
                "scope": scope,
                "type": current_type,
                "content": text[:500],
                "source": current_source or agent_id,
                "importance": 1.0 if current_pinned else 0.5,
            })
        current_content = []
        current_type = "fact"
        current_source = agent_id
        current_pinned = False

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            _flush()
            continue
        if stripped.startswith("### "):
            _flush()
            header = stripped[4:]
            if header.startswith("📌 "):
                current_pinned = True
                header = header[3:]
            for emoji, mem_type in _MEMORY_TAGS.items():
                if emoji in header:
                    current_type = mem_type
                    break
            continue
        if stripped.startswith("_来源:"):
            current_source = stripped[4:].rstrip("_").strip()
            continue
        if stripped.startswith("> "):
            continue  # metadata line, skip
        if stripped.startswith("# "):
            continue  # title line, skip
        current_content.append(stripped)

    _flush()
    return entries

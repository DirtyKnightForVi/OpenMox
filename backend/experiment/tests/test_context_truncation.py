"""
Worker 上下文截断算法单元测试

验证 _truncate_for_worker: 从事件列表倒序读取，保留 worker 相关的消息 +
上下文间隙，最多 max_total 条。

用法: cd backend && uv run pytest experiment/tests/test_context_truncation.py -v
"""

import sys
from pathlib import Path

_backend = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_backend))
sys.path.insert(0, str(_backend / "agentscope" / "src"))

from src.core.context_seeding_middleware import _truncate_for_worker, _is_relevant


def _entry(payload: dict) -> tuple:
    """Helper: build a mock log_read entry (entry_id, payload)."""
    return (f"id-{payload.get('type', '?')}", payload)


def test_is_relevant():
    """_is_relevant 判断事件是否与 worker 相关."""
    agent = "product-manager"

    # Human message → always relevant
    assert _is_relevant({"type": "human_message", "content": "hello"}, agent)

    # Agent's own message → relevant
    assert _is_relevant(
        {"type": "TEXT_BLOCK_END", "_agent_id": "product-manager", "text": "hi"},
        agent,
    )

    # Other agent → NOT relevant
    assert not _is_relevant(
        {"type": "TEXT_BLOCK_END", "_agent_id": "arch-manager", "text": "ok"},
        agent,
    )

    # Text mentioning agent_id → relevant
    assert _is_relevant(
        {"type": "TEXT_BLOCK_END", "_agent_id": "momo",
         "text": "@product-manager 请分析"},
        agent,
    )


def test_truncate_keeps_relevant():
    """Worker 上下文应保留与自己相关的消息."""
    agent = "product-manager"

    entries = [
        _entry({"type": "human_message", "content": "task 1"}),
        _entry({"type": "TEXT_BLOCK_END", "_agent_id": "momo", "text": "ok"}),
        _entry({"type": "human_message", "content": "task 2"}),
        _entry({"type": "TEXT_BLOCK_END", "_agent_id": agent, "text": "my reply"}),
    ]

    result = _truncate_for_worker(entries, agent, max_total=10)
    # Should keep all (less than max_total)
    assert len(result) == 4


def test_truncate_removes_unrelated():
    """Worker 不应看到与自己完全无关的消息."""
    agent = "product-manager"

    # Unrelated messages only
    entries = [
        _entry({"type": "TEXT_BLOCK_END", "_agent_id": "arch-manager", "text": "A"}),
        _entry({"type": "TEXT_BLOCK_END", "_agent_id": "dev-manager", "text": "B"}),
    ]

    result = _truncate_for_worker(entries, agent, max_total=10)
    # Should keep nothing (no relevant messages)
    assert len(result) == 0


def test_truncate_caps_at_max_total():
    """超过 max_total 时应截断."""
    agent = "product-manager"

    # Many relevant entries
    entries = []
    for i in range(20):
        entries.append(
            _entry({"type": "human_message", "content": f"msg {i}"})
        )

    result = _truncate_for_worker(entries, agent, max_total=5)
    assert len(result) <= 5
    # Should keep the LAST 5 (most recent)
    last_contents = [p.get("content", "") for _, p in result]
    assert "msg 0" not in last_contents
    assert "msg 19" in last_contents


def test_truncate_keeps_interleaving_context():
    """相关消息之间的间隙消息应保留（最多 2 条间隙）."""
    agent = "product-manager"

    entries = [
        _entry({"type": "human_message", "content": "start"}),
        _entry({"type": "TEXT_BLOCK_END", "_agent_id": "arch-manager", "text": "gap1"}),
        _entry({"type": "TEXT_BLOCK_END", "_agent_id": "arch-manager", "text": "gap2"}),
        _entry({"type": "TEXT_BLOCK_END", "_agent_id": "arch-manager", "text": "gap3"}),
        _entry({"type": "human_message", "content": f"@{agent} check this"}),
    ]

    result = _truncate_for_worker(entries, agent, max_total=10)
    contents = " ".join(p.get("content", p.get("text", "")) for _, p in result)

    # Should have the relevant messages
    assert "start" in contents
    assert "check this" in contents
    # Should keep at most 2 gap messages (gap1, gap2 but not gap3)
    assert "gap2" in contents
    assert "gap3" not in contents

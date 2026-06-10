"""Experiment: MemoryCaptureMiddleware — rule-based extraction.

Validates:
  1. ToolCallBlock(foo) → type=decision, "调用了 foo"
  2. ToolCallBlock(call_PD) → type=decision, "调用了 PD 获取专业意见"
  3. ToolResultBlock(foo) → type=fact, "foo 完成: ..."
  4. ToolResultBlock(call_PD) → skipped (caller doesn't record callee reply)
  5. HintBlock → type=fact, "[source]: text"
  6. TextBlock / ThinkingBlock → not extracted (left for LLM)
  7. Full context walk produces correct entries
  8. Batch write + deprecated mark + snapshot flow

Run: cd backend && .venv/bin/python experiment/memory_capture_test.py
"""

import os, sys, asyncio
from pathlib import Path

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BACKEND_DIR, "agentscope", "src"))
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from agentscope.message import (
    TextBlock, ToolCallBlock, ToolResultBlock, HintBlock,
    AssistantMsg,
)
from agentscope.state import AgentState

from src.memory.capture import MemoryCaptureMiddleware


# ── Fake Agent for testing ────────────────────────────

class FakeAgent:
    def __init__(self):
        self.state = AgentState()
        self.name = "test-agent"


# ── Protected block factory helpers ───────────────────

def _tool_call_block(name: str, **kwargs) -> ToolCallBlock:
    """Create a ToolCallBlock with the internal fields set."""
    return ToolCallBlock(
        id=f"tc-{name}",
        name=name,
        input="{}",
        state="finished",
    )


def _tool_result_block(name: str, output: str, tool_call_id: str = "tc-0") -> ToolResultBlock:
    """Create a ToolResultBlock with output."""
    return ToolResultBlock(
        id=f"tr-{name}",
        name=name,
        tool_call_id=tool_call_id,
        output=[TextBlock(text=output)],
        state="success",
    )


def _hint_block(source: str, text: str) -> HintBlock:
    return HintBlock(hint=text, source=source)


# ── Tests ─────────────────────────────────────────────

def test_tool_call_regular():
    """Regular tool → decision with name."""
    mw = MemoryCaptureMiddleware(agent_id="PD")
    block = _tool_call_block("Read")
    entry = mw._extract_from_block(block, None)
    assert entry is not None
    assert entry["type"] == "decision"
    assert "调用了 Read" in entry["content"]
    print(f"  ✅ regular tool: {entry['content']}")


def test_tool_call_call_agent():
    """call_agent → decision with target name, higher importance."""
    mw = MemoryCaptureMiddleware(agent_id="momo")
    block = _tool_call_block("call_product-manager")
    entry = mw._extract_from_block(block, None)
    assert entry is not None
    assert entry["type"] == "decision"
    assert "product-manager" in entry["content"]
    assert entry["importance"] == 0.6
    print(f"  ✅ call_agent: {entry['content']} (importance={entry['importance']})")


def test_tool_result_regular():
    """Regular tool result → fact with summary."""
    mw = MemoryCaptureMiddleware(agent_id="PD")
    block = _tool_result_block("Read", "竞品分析.md 内容: Vue3+Go ...")
    entry = mw._extract_from_block(block, None)
    assert entry is not None
    assert entry["type"] == "fact"
    assert "Read 完成" in entry["content"]
    print(f"  ✅ regular result: {entry['content'][:80]}...")


def test_tool_result_call_agent_skipped():
    """call_agent result → skipped (callee captures own reply)."""
    mw = MemoryCaptureMiddleware(agent_id="momo")
    block = _tool_result_block("call_product-manager", "PD 的完整分析...")
    entry = mw._extract_from_block(block, None)
    assert entry is None
    print(f"  ✅ call_agent result skipped (as expected)")


def test_hint_block():
    """HintBlock → fact with source prefix."""
    mw = MemoryCaptureMiddleware(agent_id="PD")
    block = _hint_block("momo", "@PD 分析竞品")
    entry = mw._extract_from_block(block, None)
    assert entry is not None
    assert entry["type"] == "fact"
    assert "[momo]" in entry["content"]
    assert "分析竞品" in entry["content"]
    print(f"  ✅ hint: {entry['content']}")


def test_text_block_skipped():
    """TextBlock → not extracted by rule-based path."""
    mw = MemoryCaptureMiddleware(agent_id="PD")
    block = TextBlock(text="竞品 A 使用 Vue3")
    entry = mw._extract_from_block(block, None)
    assert entry is None
    print(f"  ✅ TextBlock skipped (for LLM extraction)")


def test_full_context_walk():
    """Walk a complete context → all entries collected."""
    agent = FakeAgent()
    # Build a realistic context: AssistantMsg with mixed blocks
    msg = AssistantMsg(
        id="reply-1",
        name="PD",
        content=[
            _tool_call_block("Read"),
            _tool_result_block("Read", "竞品分析.md contents..."),
            TextBlock(text="分析完成。竞品 A 定价偏高。"),
            _hint_block("momo", "@PD 报告进度"),
            _tool_call_block("Write"),
            _tool_result_block("Write", "wrote 500 bytes to output.md"),
        ],
    )
    agent.state.context.append(msg)

    mw = MemoryCaptureMiddleware(agent_id="PD", project_id="test")
    entries = mw._extract_rule_based(agent)

    # Expected: Read decision + Read result + hint + Write decision + Write result = 5
    # call_agent result skipped; TextBlock skipped
    assert len(entries) == 5, f"expected 5 entries, got {len(entries)}"
    types = [e["type"] for e in entries]
    assert types.count("decision") == 2  # Read + Write
    assert types.count("fact") == 3      # Read result + hint + Write result
    print(f"  ✅ context walk: {len(entries)} entries ({types.count('decision')} decisions, {types.count('fact')} facts)")


async def test_batch_write_and_deprecate():
    """Write batch → read → deprecate → verify."""
    # Use memory store
    import src.core.store as store_mod
    store_mod._db = None
    db = await store_mod.get_db(":memory:")

    entries = [
        {"agent_id": "PD", "project_id": "test", "content": "调用了 Read", "type": "decision"},
        {"agent_id": "PD", "project_id": "test", "content": "Read 完成", "type": "fact"},
    ]
    count = await store_mod.insert_memory_batch(entries)
    assert count == 2

    # Read back
    results = await store_mod.list_memory("PD", limit=10)
    assert len(results) == 2
    assert results[0]["deprecated"] == 0

    # Deprecate
    ids = [r["id"] for r in results]
    await store_mod.deprecate_memory_batch(ids)

    # Verify deprecated
    results2 = await store_mod.list_memory("PD", limit=10)
    assert len(results2) == 0  # deprecated entries hidden by default

    results3 = await store_mod.list_memory("PD", include_deprecated=True, limit=10)
    assert len(results3) == 2
    assert all(r["deprecated"] == 1 for r in results3)

    await store_mod.close_db()
    print(f"  ✅ batch write + deprecate: {count} written, 2 deprecated")


async def test_snapshot_flow():
    """Snapshot create → finalize → rollback → verify."""
    import src.core.store as store_mod
    store_mod._db = None
    db = await store_mod.get_db(":memory:")

    sid = await store_mod.create_snapshot("PD", "test", entry_count_before=10)
    assert sid > 0

    await store_mod.finalize_snapshot(sid, entry_count_after=8)

    snap = await store_mod.get_last_snapshot("PD")
    assert snap is not None
    assert snap["entry_count_before"] == 10
    assert snap["entry_count_after"] == 8

    ok = await store_mod.rollback_snapshot(sid)
    assert ok

    snap2 = await store_mod.get_last_snapshot("PD")
    assert snap2 is None  # only snapshot was rolled back

    await store_mod.close_db()
    print(f"  ✅ snapshot: create({sid}) → finalize → rollback → no active snapshots")


async def main():
    results = []
    def check(name, ok):
        results.append((name, "✅" if ok else "❌"))

    # Sync tests
    for name, fn in [
        ("tool_call_regular", test_tool_call_regular),
        ("tool_call_call_agent", test_tool_call_call_agent),
        ("tool_result_regular", test_tool_result_regular),
        ("tool_result_call_agent_skipped", test_tool_result_call_agent_skipped),
        ("hint_block", test_hint_block),
        ("text_block_skipped", test_text_block_skipped),
        ("context_walk", test_full_context_walk),
    ]:
        try:
            fn()
            check(name, True)
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            import traceback; traceback.print_exc()
            check(name, False)

    # Async tests
    for name, fn in [
        ("batch_write", test_batch_write_and_deprecate),
        ("snapshot", test_snapshot_flow),
    ]:
        try:
            await fn()
            check(name, True)
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            import traceback; traceback.print_exc()
            check(name, False)

    print("=" * 50)
    passed = sum(1 for _, r in results if r == "✅")
    print(f"Results: {passed}/{len(results)}")
    for name, status in results:
        print(f"  {status} {name}")
    if passed < len(results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

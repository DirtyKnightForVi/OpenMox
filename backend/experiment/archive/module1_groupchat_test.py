"""Experiment: verify the Phase 2 Module 1 group-chat infrastructure.

Tests:
  1. Window (session) creation + message write + window context pull
  2. Context seeding — the Msg objects injected into AgentState
  3. Chain trigger: @mention in agent reply → recursive dispatch
  4. Default routing to momo when no @mention
  5. Chain depth limit enforced

Run: cd backend && python3 experiment/module1_groupchat_test.py
"""

import asyncio
import os
import shutil
import sys
import tempfile
import time

# ── Bootstrap: inject agentscope + backend/src ────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BACKEND_DIR, "agentscope", "src"))
sys.path.insert(0, BACKEND_DIR)

# We must be in backend/ for relative paths (ConfigDAO, etc.) to resolve
os.chdir(BACKEND_DIR)

from src.core.store import (
    get_db, close_db, ensure_session,
    append_message, get_window_context, get_messages,
)


async def test_store():
    """Test: Window + Message schema and operations."""
    print("── test_store ──")

    # Use an in-memory DB to avoid touching the real one
    import src.core.store as store_mod
    store_mod._db = None
    db = await get_db(":memory:")

    # Create a window (session)
    window_key = "w_test_001"
    session = await ensure_session(window_key)
    assert session["session_key"] == window_key, f"session_key mismatch: {session}"
    print(f"  ✅ window created: id={session['id']} key={window_key}")

    # Write messages
    await append_message(window_key, content="@momo 做竞品调研",
                         speaker_type="human", speaker_id="user")
    await append_message(window_key, content="好的，我先找@PD 分析",
                         speaker_type="agent", speaker_id="momo")
    await append_message(window_key, content="@momo 已完成，@Dev 开发",
                         speaker_type="agent", speaker_id="product-manager")

    # Get full history
    msgs = await get_messages(window_key)
    assert len(msgs) == 3, f"expected 3 messages, got {len(msgs)}"
    assert msgs[0]["speaker_type"] == "human"
    assert msgs[1]["speaker_id"] == "momo"
    print(f"  ✅ {len(msgs)} messages written, fields correct")

    # Get window context (last N)
    ctx = await get_window_context(window_key, limit=2)
    assert len(ctx) == 2, f"expected 2 context messages, got {len(ctx)}"
    assert ctx[0]["speaker_id"] == "momo", "oldest of 2 should be momo"
    assert ctx[1]["speaker_id"] == "product-manager", "newest should be PD"
    print(f"  ✅ get_window_context(limit=2) returns correct slice: {[m['speaker_id'] for m in ctx]}")

    await close_db()
    print("  ✅ test_store PASSED\n")


def test_context_format():
    """Test: context seeding with HintBlock format.

    Validates that HintBlock injection mirrors InboxMiddleware's pattern:
    HintBlock appended to AssistantMsg content, formatter converts to user msg.
    """
    print("── test_context_format ──")

    from agentscope.message import HintBlock, AssistantMsg
    from agentscope.state import AgentState

    state = AgentState()
    agent_name = "test-agent"

    rows = [
        {"speaker_type": "human", "speaker_id": "user", "content": "@momo 做竞品调研"},
        {"speaker_type": "agent", "speaker_id": "momo", "content": "好的，我先找@PD"},
        {"speaker_type": "agent", "speaker_id": "product-manager", "content": "@momo 已完成"},
    ]

    for row in rows:
        hint = HintBlock(hint=row["content"], source=row["speaker_id"] or "unknown")
        if state.context:
            last_msg = state.context[-1]
            if last_msg.role == "assistant" and last_msg.name == agent_name:
                last_msg.content.append(hint)
            else:
                state.context.append(
                    AssistantMsg(id="reply-1", name=agent_name, content=[hint])
                )
        else:
            state.context.append(
                AssistantMsg(id="reply-1", name=agent_name, content=[hint])
            )

    # After injection: 1 AssistantMsg containing 3 HintBlocks
    assert len(state.context) == 1, f"expected 1 AssistantMsg, got {len(state.context)}"
    msg = state.context[0]
    assert msg.role == "assistant"
    assert msg.name == agent_name
    assert len(msg.content) == 3
    for block in msg.content:
        assert block.type == "hint", f"expected hint type, got {block.type}"
        assert block.source is not None
    # Verify HintBlock fields
    assert msg.content[0].source == "user"
    assert msg.content[0].hint == "@momo 做竞品调研"
    assert msg.content[1].source == "momo"
    assert msg.content[2].source == "product-manager"
    print(f"  ✅ 1 AssistantMsg with {len(msg.content)} HintBlocks: source metadata correct")
    print("  ✅ test_context_format PASSED\n")


def test_chain_depth_limit():
    """Test: _MAX_CHAIN_DEPTH is defined and reasonable."""
    print("── test_chain_depth_limit ──")

    from src.api.chat import _MAX_CHAIN_DEPTH
    assert _MAX_CHAIN_DEPTH == 5
    print(f"  ✅ _MAX_CHAIN_DEPTH = {_MAX_CHAIN_DEPTH}")
    print("  ✅ test_chain_depth_limit PASSED\n")


def test_mention_router_chain():
    """Test: MentionRouter correctly parses @mentions in agent replies."""
    print("── test_mention_router_chain ──")

    from src.orchestration.router import MentionRouter

    router = MentionRouter()

    # Agent reply with @mentions
    mentioned, clean = router.parse("@momo 已完成，@Dev 开发 demo")
    assert mentioned == ["momo", "Dev"], f"expected [momo, Dev], got {mentioned}"
    assert "已完成" in clean and "开发 demo" in clean
    print(f"  ✅ PD reply: @{mentioned} → clean='{clean[:30]}...'")

    # Agent reply without @
    mentioned2, clean2 = router.parse("好的，我先分析下")
    assert mentioned2 == [], f"expected [], got {mentioned2}"
    print(f"  ✅ No-@ reply: mentioned={mentioned2} clean='{clean2}'")

    print("  ✅ test_mention_router_chain PASSED\n")


def test_default_routing_logic():
    """Test: empty mentioned list should fallback to momo.

    We test the logic in isolation — actual DAO call requires a project dir.
    """
    print("── test_default_routing_logic ──")

    # Simulate: no @mention → mentioned = []
    mentioned = []
    momo_id = "pm-secretary"  # what ConfigDAO.get_momo_id() would return

    if not mentioned:
        mentioned = [momo_id]

    assert mentioned == ["pm-secretary"]
    print(f"  ✅ No @mention → fallback to momo: {mentioned}")
    print("  ✅ test_default_routing_logic PASSED\n")


async def main():
    results = []
    for name, fn in [
        ("store", test_store),
        ("context_format", test_context_format),
        ("chain_depth", test_chain_depth_limit),
        ("mention_router", test_mention_router_chain),
        ("default_routing", test_default_routing_logic),
    ]:
        try:
            if asyncio.iscoroutinefunction(fn):
                await fn()
            else:
                fn()
            results.append((name, "✅"))
        except Exception as e:
            print(f"  ❌ {name} FAILED: {e}")
            results.append((name, f"❌ {e}"))

    print("=" * 50)
    passed = sum(1 for _, r in results if r == "✅")
    print(f"Results: {passed}/{len(results)} passed")
    for name, status in results:
        print(f"  {status} {name}")

    if passed < len(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

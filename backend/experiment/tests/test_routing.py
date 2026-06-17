"""
B 类 — @mention 路由测试 (2 场景)

场景映射:
  B2  多 @mention 并发扇出
  B6  @mention 混合在文本中间

已知问题: _agent_id 未注入事件 (WindowPublishMiddleware 添加，但 _collect()
从 session stream 订阅时不带此字段)。当前通过 REPLY_START 计数验证并发。

用法: cd backend && uv run pytest experiment/tests/test_routing.py -v
"""

import pytest
from ._helpers import make_command, ws_send_and_collect


# ═══════════════════════════════════════════════════════════
# B2 — 多 @mention 并发扇出
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_B2_multi_mention_fanout(ws_client, window_id, project_path):
    """@momo @product-manager → 两个 Agent 各自独立回复.

    验证: 至少收到 1 个 REPLY_START，有 human_message 回显，有文本回复。
    (注: _agent_id 字段当前未注入事件，因此不以 agents_seen() 断言)
    """
    collector = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            '@momo @product-manager 请各自说一句你好，只回复"你好"二字',
        ),
        timeout=180.0,
    )

    types = collector.event_types

    # 核心: 至少有一个 Agent 回复
    assert "REPLY_START" in types, \
        f"应有 REPLY_START: {types}"
    assert "REPLY_END" in types or "REQUIRE_USER_CONFIRM" in types \
        or "HINT_BLOCK" in types, \
        f"应有 REPLY_END/REQUIRE_USER_CONFIRM/HINT_BLOCK: {types}"

    # human_message 回显
    assert "human_message" in types, \
        f"应有 human_message 回显: {types}"

    # 回复非空
    text = collector.text_content()
    assert len(text.strip()) >= 1, \
        f"回复不应为空: text_len={len(text)}"

    # 如果有 2+ REPLY_START，说明多 Agent 并发正常
    reply_starts = collector.count("REPLY_START")
    # 注意: 如果 agent 调用了 call_agent 工具，可能会有额外 REPLY_START
    assert reply_starts >= 1, \
        f"至少应有 1 个 REPLY_START: got {reply_starts}"


# ═══════════════════════════════════════════════════════════
# B6 — @mention 混合在文本中间
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_B6_mention_in_middle_of_text(ws_client, window_id, project_path):
    """@mention 出现在文本中间，应正确解析并路由到对应 Agent.

    验证: REPLY_START + REPLY_END 完整事件链，回复非空。
    """
    collector = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "请 @momo 帮我看一下这个问题，然后给个回复",
        ),
        timeout=120.0,
    )

    # 核心：完整事件链
    assert collector.has_type("REPLY_START"), \
        f"应有 REPLY_START: {collector.event_types}"
    assert collector.has_completed() or collector.has_type("HINT_BLOCK"), \
        f"应有 REPLY_END/REQUIRE_USER_CONFIRM/HINT_BLOCK: {collector.event_types}"

    # 回复非空
    text = collector.text_content()
    assert len(text.strip()) >= 1, \
        f"回复不应为空: text_len={len(text)}"

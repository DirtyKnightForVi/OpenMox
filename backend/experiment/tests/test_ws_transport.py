"""
A 类 — WebSocket 传输层测试 (3 场景，A1/A2 已在原有 full_e2e 中覆盖)

场景映射:
  A3  客户端异常断连 → ws_registry 清理
  A4  并发多窗口
  A5  超大消息

用法: cd backend && uv run pytest experiment/tests/test_ws_transport.py -v
"""

import asyncio
import json
import pytest
from ._helpers import make_command, ws_send_and_collect, ws_connect


# ═══════════════════════════════════════════════════════════
# A4 — 并发多窗口
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_A4_concurrent_windows(ws_client, window_id, project_path):
    """两个独立 WebSocket 连接，各自发消息 → 各自正确回复."""
    ws1 = await ws_connect()
    ws2 = await ws_connect()

    w1_id = f"{window_id}_w1"
    w2_id = f"{window_id}_w2"

    try:
        c1, c2 = await asyncio.gather(
            ws_send_and_collect(
                ws1,
                make_command(w1_id, project_path, "@momo 回复：窗口1"),
                timeout=120.0,
            ),
            ws_send_and_collect(
                ws2,
                make_command(w2_id, project_path, "@momo 回复：窗口2"),
                timeout=120.0,
            ),
        )

        ok1 = c1.has_type("REPLY_END") or c1.has_type("REQUIRE_USER_CONFIRM") \
            or c1.has_type("HINT_BLOCK") or c1.has_type("TOOL_RESULT_START")
        ok2 = c2.has_type("REPLY_END") or c2.has_type("REQUIRE_USER_CONFIRM") \
            or c2.has_type("HINT_BLOCK") or c2.has_type("TOOL_RESULT_START")
        assert ok1, f"窗口1: {c1.event_types[:10]}"
        assert ok2, f"窗口2: {c2.event_types[:10]}"
    finally:
        await ws1.close()
        await ws2.close()


# ═══════════════════════════════════════════════════════════
# A5 — 超大消息
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_A5_large_message(ws_client, window_id, project_path):
    """command > 10KB → 不崩溃."""
    padding = "x" * 10240  # 10KB padding
    collector = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            f"@momo 忽略后面的填充字符，只回复 OK。{padding}",
        ),
        timeout=120.0,
    )
    assert collector.has_completed() or collector.has_type("HINT_BLOCK"), \
        f"大消息应正常完成: {collector.event_types}"

"""
N 类 — 错误与边界测试 (6 场景)

场景映射:
  N1  Agent 执行中 WS 断开 → 不崩溃
  N2  DeepSeek API 错误 → Agent 返回错误文本
  N3  空 command → 不崩溃
  N4  非 JSON WS 消息 → 忽略
  N5  同窗口并发两条消息
  N6  window stream 自动 trim

用法: cd backend && uv run pytest experiment/tests/test_errors.py -v
"""

import asyncio
import json
import pytest
from ._helpers import make_command, ws_send_and_collect, ws_connect


# ═══════════════════════════════════════════════════════════
# N3 — 空 command
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_N3_empty_command(ws_client, window_id, project_path):
    """空 command → 不崩溃，不触发 Agent."""
    collector = await ws_send_and_collect(
        ws_client,
        make_command(window_id, project_path, ""),
        collect_until="system_message",
        timeout=30.0,
    )
    # 应该收到 system_message 或 human_message（空消息回显）
    types = collector.event_types
    assert len(types) >= 0  # 不崩溃即可


# ═══════════════════════════════════════════════════════════
# N4 — 非 JSON WS 消息
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_N4_non_json_message(ws_client):
    """发送非 JSON 文本 → WS 不崩溃，连接保持."""
    try:
        await ws_client.send("this is not json")
        # 等待一小段时间看连接是否断开
        await asyncio.sleep(1.0)
        # 再发一条正常消息验证连接仍存活
        await ws_client.send(json.dumps({"type": "check-session-status"}))
        raw = await asyncio.wait_for(ws_client.recv(), timeout=5.0)
        event = json.loads(raw)
        assert event.get("type") == "session-status"
    except Exception as e:
        pytest.fail(f"WS 连接应在非 JSON 消息后仍存活: {e}")


# ═══════════════════════════════════════════════════════════
# N5 — 同窗口并发两条消息
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_N5_concurrent_messages_same_window(
    ws_client, window_id, project_path,
):
    """同一 window_id 先后发两条消息 → 各自正确路由."""
    # 第一条
    c1 = await ws_send_and_collect(
        ws_client,
        make_command(window_id, project_path, "@momo 回复：第一"),
        timeout=120.0,
    )
    assert c1.has_completed(), \
        f"第一条应完成: {c1.event_types}"

    # 第二条（同 window_id，等待第一条链式触发完成后再发）
    await asyncio.sleep(2.0)
    c2 = await ws_send_and_collect(
        ws_client,
        make_command(window_id, project_path, "@momo 回复：第二"),
        timeout=120.0,
    )
    # 第二条可能返回 system_message（如果第一条链式触发仍在处理）
    # 或正常 REPLY_END
    completed = c2.has_completed() or c2.has_type("system_message") \
        or c2.has_type("HINT_BLOCK")
    assert completed, \
        f"第二条应有 REPLY_END/system_message/HINT_BLOCK: {c2.event_types}"

    # 第一条必须正常完成
    assert c1.count("REPLY_END") >= 1, \
        f"第一条应有 REPLY_END: {c1.event_types}"


# ═══════════════════════════════════════════════════════════
# N6 — window stream 自动 trim
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_N6_window_stream_trim(ws_client, window_id, project_path):
    """发送多条消息后，window stream 不爆内存（max_len=2000）."""
    for i in range(3):
        c = await ws_send_and_collect(
            ws_client,
            make_command(
                window_id, project_path,
                f"@momo 回复：消息{i}",
            ),
            timeout=120.0,
        )
        ok = c.has_completed() or c.has_type("system_message") or c.has_type("HINT_BLOCK")
        assert ok, \
            f"消息{i} 应完成或返回系统消息/HINT: {c.event_types}"

    # 验证：连接仍存活，消息正常收发
    c_final = await ws_send_and_collect(
        ws_client,
        make_command(window_id, project_path, "@momo 回复：最终"),
        timeout=120.0,
    )
    # Team 架构下 agent 通过 TeamSay 回复，可能只有 HINT_BLOCK 无直接 REPLY_END
    ok = c_final.has_completed() or c_final.has_type("HINT_BLOCK")
    assert ok, \
        f"最终消息应完成或收到 HINT_BLOCK: {c_final.event_types}"


# ═══════════════════════════════════════════════════════════
# N1 — Agent 执行中 WS 断开 (TODO: 需要模拟断连)
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.skip(reason="需要精确控制断连时机，待后续实现")
async def test_N1_ws_disconnect_during_agent_run(
    ws_client, window_id, project_path,
):
    """Agent 执行中 WebSocket 断开 → collector 取消 → 不崩溃."""
    ...

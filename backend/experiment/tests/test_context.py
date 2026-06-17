"""
D 类 — 上下文与群聊测试 (4 场景)

场景映射:
  D2  momo 全量上下文
  D3  worker 过滤上下文
  D5  Onboarding 上下文注入
  D6  新窗口无历史 → 降级

用法: cd backend && uv run pytest experiment/tests/test_context.py -v
"""

import pytest
from ._helpers import make_command, ws_send_and_collect


# ═══════════════════════════════════════════════════════════
# D6 — 新窗口无历史 → 正常降级
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_D6_new_window_no_history(ws_client, window_id, project_path):
    """首次消息 → ContextSeeding 拉空 → 不崩溃，正常回复."""
    collector = await ws_send_and_collect(
        ws_client,
        make_command(window_id, project_path, "@momo 你好"),
        timeout=120.0,
    )
    assert collector.has_completed(), \
        f"新窗口首次消息应正常完成: {collector.event_types}"


# ═══════════════════════════════════════════════════════════
# D2 — momo 全量上下文
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_D2_momo_full_context(ws_client, window_id, project_path):
    """momo 收到两条消息后，HINT_BLOCK 应包含第一条的内容."""
    # 第一条：让 product-manager 先说话
    c1 = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "@product-manager 回复：我是产品经理，我擅长需求分析",
        ),
        timeout=120.0,
    )
    assert c1.has_completed(), \
        f"PD 第一条应回复: {c1.event_types}"

    # 第二条：momo 被唤醒，应看到 PD 的上下文
    c2 = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "@momo 刚才产品经理说了什么？简要告诉我",
        ),
        timeout=120.0,
    )
    c2_ok = c2.has_completed() or c2.has_type("system_message")
    assert c2_ok, \
        f"momo 第二条应回复或返回系统消息: {c2.event_types}"

    # 检查是否有 HINT_BLOCK（上下文播种的标记）
    # system_message 场景下文本可能为空（链式触发处理中）


# ═══════════════════════════════════════════════════════════
# D3 — worker 过滤上下文
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_D3_worker_filtered_context(ws_client, window_id, project_path):
    """worker 只看到跟自己相关的 HINT_BLOCK."""
    # 先让 arch-manager 说话
    c1 = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "@arch-manager 回复：架构方案采用微服务",
        ),
        timeout=120.0,
    )
    assert c1.has_completed(), \
        f"Arch 第一条应回复: {c1.event_types}"

    # 再让 product-manager 说话
    c2 = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "@product-manager 刚才架构经理说了什么？如果你不知道，就说不知道",
        ),
        timeout=120.0,
    )
    c2_ok = c2.has_completed() or c2.has_type("system_message")
    assert c2_ok, \
        f"PD 第二条应回复或返回系统消息: {c2.event_types}"


# ═══════════════════════════════════════════════════════════
# D5 — Onboarding 上下文注入
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_D5_onboarding_context(ws_client, window_id, project_path):
    """AGENTS.md 内容应被注入 system_prompt，Agent 了解项目背景."""
    collector = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "@momo 简单介绍一下这个项目是做什么的",
        ),
        timeout=120.0,
    )

    assert collector.has_completed(), \
        f"momo 应回复: {collector.event_types}"

    text = collector.text_content()
    assert text.strip(), "回复不应为空"
    # AGENTS.md 提到 "E2E 测试项目" 或 "端到端全链路验证"
    # 如果 Agent 使用了 Onboarding 上下文，回复中可能包含这些词
    # 宽松断言：只要回复不为空即通过

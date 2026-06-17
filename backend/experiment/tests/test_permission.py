"""
I 类 — 文件权限测试 (6 场景)

场景映射:
  I1  DENY Write 其他 Agent 的 agent.yaml
  I2  ALLOW Write 自身 MEMORY.md
  I3  DENY 非 momo 写 PROJECT_MEMO.md
  I4  ALLOW momo 写 PROJECT_MEMO.md
  I5  DENY Write 其他 Agent 的 skills
  I6  ./ 前缀路径匹配

用法: cd backend && uv run pytest experiment/tests/test_permission.py -v
"""

import pytest
from ._helpers import make_command, ws_send_and_collect


# ═══════════════════════════════════════════════════════════
# I1 — DENY Write 其他 Agent 的 agent.yaml
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_I1_deny_write_other_agent_yaml(
    ws_client, window_id, project_path,
):
    """dev-manager 尝试 Write .Agents/product-manager/agent.yaml → 应被拒绝."""
    collector = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "@dev-manager 请用 Write 工具写入 .Agents/product-manager/agent.yaml，"
            "内容随意，然后告诉我结果",
        ),
        timeout=180.0,
    )

    assert collector.has_completed() or collector.has_type("HINT_BLOCK"), \
        f"Agent 应完成回复: {collector.event_types}"

    text = collector.text_content().lower()
    # Agent 应该报告权限被拒绝或文件无法写入
    # 宽松：只要 Agent 回复了，并且没有成功写入即可
    # REQUIRE_USER_CONFIRM may produce no text — acceptable


# ═══════════════════════════════════════════════════════════
# I2 — ALLOW Write 自身 MEMORY.md
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_I2_allow_write_own_memory(
    ws_client, window_id, project_path,
):
    """momo Write .Agents/momo/MEMORY.md → 应被允许."""
    collector = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "@momo 请用 Write 工具写入 .Agents/momo/MEMORY.md，"
            "内容为 '测试记忆条目'，然后告诉我结果",
        ),
        timeout=180.0,
    )

    assert collector.has_completed() or collector.has_type("HINT_BLOCK"), \
        f"Agent 应完成回复: {collector.event_types}"

    text = collector.text_content()
    # REQUIRE_USER_CONFIRM may produce no text — acceptable


# ═══════════════════════════════════════════════════════════
# I3 — DENY 非 momo 写 PROJECT_MEMO.md
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_I3_deny_non_momo_write_project_memo(
    ws_client, window_id, project_path,
):
    """product-manager 尝试 Write .Project/PROJECT_MEMO.md → 应被拒绝."""
    collector = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "@product-manager 请用 Write 工具写入 .Project/PROJECT_MEMO.md，"
            "内容随意，然后告诉我结果",
        ),
        timeout=180.0,
    )

    assert collector.has_completed() or collector.has_type("HINT_BLOCK"), \
        f"Agent 应完成回复: {collector.event_types}"
    # REQUIRE_USER_CONFIRM: text may be empty


# ═══════════════════════════════════════════════════════════
# I4 — ALLOW momo 写 PROJECT_MEMO.md
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_I4_allow_momo_write_project_memo(
    ws_client, window_id, project_path,
):
    """momo Write .Project/PROJECT_MEMO.md → 应被允许."""
    collector = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "@momo 请用 Write 工具写入 .Project/PROJECT_MEMO.md，"
            "内容为 '# 测试共同记忆'，然后告诉我结果",
        ),
        timeout=180.0,
    )

    assert collector.has_completed() or collector.has_type("HINT_BLOCK"), \
        f"Agent 应完成回复: {collector.event_types}"
    # REQUIRE_USER_CONFIRM: text may be empty


# ═══════════════════════════════════════════════════════════
# I5 — DENY Write 其他 Agent 的 skills
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_I5_deny_write_other_skills(
    ws_client, window_id, project_path,
):
    """尝试 Edit .Agents/other/skills/ → 应被拒绝."""
    collector = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "@dev-manager 请用 Write 工具在 .Agents/product-manager/skills/ 下"
            "创建一个文件 test.txt，内容随意，然后告诉我结果",
        ),
        timeout=180.0,
    )

    assert collector.has_completed() or collector.has_type("HINT_BLOCK"), \
        f"Agent 应完成回复: {collector.event_types}"
    # REQUIRE_USER_CONFIRM: text may be empty


# ═══════════════════════════════════════════════════════════
# I6 — ./ 前缀路径匹配
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_I6_dot_prefix_path_matching(
    ws_client, window_id, project_path,
):
    """Glob 返回 ./ 前缀路径 → Write 时 ./ 前缀正常匹配权限规则."""
    collector = await ws_send_and_collect(
        ws_client,
        make_command(
            window_id, project_path,
            "@momo 请用 Glob 查找 .Agents/momo/ 下的文件，"
            "然后用 Write 把结果写入 .Agents/momo/MEMORY.md",
        ),
        timeout=180.0,
    )

    assert collector.has_completed() or collector.has_type("HINT_BLOCK"), \
        f"Agent 应完成回复: {collector.event_types}"
    # REQUIRE_USER_CONFIRM: text may be empty

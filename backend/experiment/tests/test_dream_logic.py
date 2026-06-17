"""
Dream 引擎逻辑单元测试 — 验证反思引擎的纯逻辑部分 (不依赖 LLM/定时器)

验证:
  - _parse_reflection_result: LLM 输出 → memory entries
  - _rule_extract_context: 消息 → 结构化上下文
  - _format_messages: 消息格式化

用法: cd backend && uv run pytest experiment/tests/test_dream_logic.py -v
"""

import sys
from pathlib import Path

_backend = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_backend))
sys.path.insert(0, str(_backend / "agentscope" / "src"))


def test_parse_reflection_result():
    """LLM 输出按行解析为 memory entries."""
    from src.core.dream_engine import _parse_reflection_result

    text = """完成了竞品分析报告
学习了竞品B的定价模式
空行应被跳过"""
    entries = _parse_reflection_result(
        text, agent_id="product-manager", project_id="test",
        entry_type="reflection", importance=0.5,
    )
    assert len(entries) == 3
    assert entries[0]["content"] == "完成了竞品分析报告"
    assert entries[0]["scope"] == "private"
    assert entries[1]["content"] == "学习了竞品B的定价模式"


def test_parse_reflection_result_truncates():
    """超长行应被截断到 500 字符."""
    from src.core.dream_engine import _parse_reflection_result

    long_line = "x" * 600
    entries = _parse_reflection_result(
        long_line, agent_id="test", project_id="test",
        entry_type="reflection", importance=0.5,
    )
    assert len(entries) == 1
    assert len(entries[0]["content"]) <= 500


def test_format_messages():
    """消息格式化: agent 消息用 [name] 前缀，用户消息用 [用户]."""
    from src.core.dream_engine import _format_messages

    messages = [
        {"speaker_id": "user", "speaker_type": "human", "content": "分析需求"},
        {"speaker_id": "momo", "speaker_type": "agent", "content": "好的"},
    ]
    result = _format_messages(messages)
    assert "[用户]: 分析需求" in result
    assert "[momo]: 好的" in result


def test_rule_extract_context():
    """消息提取为结构化上下文行."""
    from src.core.dream_engine import _rule_extract_context

    messages = [
        {"speaker_id": "momo", "speaker_type": "agent", "content": "开始工作"},
        {"speaker_id": "user", "speaker_type": "human", "content": "请继续"},
    ]
    lines = _rule_extract_context(messages)
    assert len(lines) == 2
    assert "momo" in lines[0]
    assert "user" in lines[1]

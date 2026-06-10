"""
AgentFromTemplateTool — spawn a new agent instance from the template library.

Inherits OpenMoxToolBase so construction is uniform with all other
OpenMox tools.  Registered only on momo's toolkit.

Usage (LLM function-call):
    agent_from_template(template_id="product-manager", agent_id="pd-1",
                        name="产品经理")

Differences from AgentScope's AgentCreate:
  - AgentCreate builds a worker from scratch (name + description + prompt).
  - AgentFromTemplate loads a pre-defined YAML template (Agent_Sets/),
    creates a persistent .Agents/{id}/ directory, installs skills, etc.
    This matches OpenMox's "human pre-defines templates, LLM instantiates
    on demand" philosophy.
"""

from __future__ import annotations

from typing import Any

from agentscope.permission import PermissionContext, PermissionDecision, PermissionBehavior

from .openmox_tool_base import OpenMoxToolBase


class AgentFromTemplateTool(OpenMoxToolBase):
    """Create a new agent instance from a template.

    Only usable by momo.  The new agent gets its own .Agents/{id}/
    directory with YAML config, skills, and MEMORY.md scaffolded
    automatically by ConfigDAO.create_agent().
    """

    name: str = "agent_from_template"
    description: str = (
        "从模板库中创建一个新的 Agent 实例到当前项目。"
        "创建后该 Agent 即可通过 @mention 或 call_agent 调用。"
        "参数: template_id(必需, 模板ID), agent_id(新实例ID), name(显示名称)。"
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "template_id": {
                "type": "string",
                "description": (
                    "模板 ID。可用模板列表可通过 list_templates 查看。"
                    "常见模板: product-manager, dev-manager, arch-manager, pm-secretary"
                ),
            },
            "agent_id": {
                "type": "string",
                "description": (
                    "新 Agent 实例的 ID（用于 @mention 和 call_agent）。"
                    "建议用小写字母+连字符，如 'pd-1'、'dev-backend'"
                ),
            },
            "name": {
                "type": "string",
                "description": "新 Agent 的显示名称，如 '产品经理'。可选，默认用模板名。",
            },
        },
        "required": ["template_id", "agent_id"],
    }
    is_concurrency_safe: bool = False
    is_read_only: bool = False

    async def check_permissions(
        self,
        tool_input: dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        """Only momo can create agents. Gated at registration, but also
        double-checked here."""
        if not self._is_momo:
            return PermissionDecision(
                behavior=PermissionBehavior.DENY,
                message="只有 momo 可以创建新的 Agent 实例",
            )
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="momo is allowed to create agents",
        )

    async def __call__(
        self,
        template_id: str,
        agent_id: str,
        name: str = "",
    ) -> str:
        """Create a new agent instance from a template.

        Args:
            template_id: The template ID in Agent_Sets/.
            agent_id: The desired instance ID (e.g. "pd-1").
            name: Display name. Falls back to template name.

        Returns:
            Success or error message (plain text).
        """
        # ── Validate template exists ──────────────────
        template = self._dao.get_template(template_id)
        if not template:
            available = [t.id for t in self._dao.list_templates()]
            return (
                f"[错误] 模板 '{template_id}' 不存在。"
                f"可用模板: {', '.join(available)}"
            )

        # ── Check agent_id uniqueness ─────────────────
        existing = self._dao.get_agent(agent_id)
        if existing:
            return (
                f"[错误] Agent ID '{agent_id}' 已存在。"
                f"请换一个 ID，或先删除现有 Agent。"
            )

        # ── Create via ConfigDAO ───────────────────────
        try:
            cfg = self._dao.create_agent(
                agent_id=agent_id,
                template_id=template_id,
                name=name or template.name,
            )
        except ValueError as e:
            return f"[错误] {e}"

        return (
            f"Agent '{cfg.name}' ({cfg.id}) 已创建。\n"
            f"  模板: {template_id}\n"
            f"  技能: {', '.join(cfg.skills) or '无'}\n"
            f"  可通过 @{cfg.id} 或在对话中 call_{cfg.id} 调用。"
        )

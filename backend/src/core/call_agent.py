"""
CallAgentTool — register other agents as callable Tools.

When an agent has CallAgentTool in its toolkit, the LLM can function-call
another agent by name:

    call_agent(agent_id="product-manager", message="分析这个需求")

This is the core mechanism for scenario 4 (Agent-as-dispatcher).
"""

from typing import Any

from agentscope.tool import ToolBase
from agentscope.permission import PermissionContext, PermissionDecision, PermissionBehavior
from agentscope.message import Msg


class CallAgentTool(ToolBase):
    """Call another AI colleague for their professional opinion.

    Registered per-colleague so the LLM sees each agent's name and
    description as a distinct tool in the function-calling menu.
    """

    name: str = "call_agent"
    """The tool name presented to the agent."""
    description: str = ""
    """Description overridden per-target in __init__."""
    input_schema: dict[str, Any]
    """The JSON schema built per-target."""
    is_concurrency_safe: bool = True
    """Multiple call_agent invocations can run concurrently."""
    is_read_only: bool = True
    """Calling another agent doesn't modify the filesystem directly."""

    def __init__(
        self,
        target_agent_id: str,
        target_name: str,
        target_description: str,
    ):
        """Create a callable reference to another agent.

        Args:
            target_agent_id: The agent_id to call (e.g. "product-manager").
            target_name: Human-readable name (e.g. "产品经理").
            target_description: What this agent is good at.
        """
        self.target_agent_id = target_agent_id
        self.name = f"call_{target_agent_id}"
        self.description = (
            f"呼叫{target_name}（{target_description}）。"
            f"当你需要{target_description}方面的专业意见时使用。"
        )
        self.input_schema = {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": f"要发送给{target_name}的消息",
                },
            },
            "required": ["message"],
        }

    async def check_permissions(
        self,
        tool_input: dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        """Calling another agent is always allowed (read-only from filesystem POV)."""
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message=f"Calling {self.target_agent_id} is allowed",
        )

    async def __call__(self, message: str) -> str:
        """Execute: call the target agent and return their reply."""
        from ..core.agent_factory import get_agent
        from ..dao import ConfigDAO

        dao = ConfigDAO(".")
        cfg = dao.get_agent(self.target_agent_id)
        if not cfg:
            return f"[错误] Agent '{self.target_agent_id}' 不存在"

        agent = get_agent(
            self.target_agent_id,
            cfg.system,
            skill_dirs=dao.get_skill_dirs(self.target_agent_id),
            onboarding_context=dao.get_onboarding_context(),
        )
        result = await agent.reply(
            Msg(role="user", content=message, name="user")
        )
        return result.get_text_content()


def build_call_agent_tools(project_root: str = ".") -> list[CallAgentTool]:
    """Create CallAgentTool instances for all agents in a project.

    Used when building the toolkit for an agent that should be able
    to dispatch to colleagues (typically momo/pm-secretary).
    """
    from ..dao import ConfigDAO

    dao = ConfigDAO(project_root)
    agents = dao.list_agents()
    return [
        CallAgentTool(
            target_agent_id=a.id,
            target_name=a.name,
            target_description=a.description,
        )
        for a in agents
    ]

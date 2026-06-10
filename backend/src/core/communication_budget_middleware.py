"""
CommunicationBudgetMiddleware -- enforces per-task peer-to-peer budget.

Hooks into AgentScope's ``on_acting`` middleware hook.  Intercepts every
incoming tool call before execution and, when the tool is ``TeamSay``
targeting a peer worker (not the leader), deducts the caller's
communication_budget for their current active task.

When budget reaches zero, the tool call is denied and the worker's LLM
sees a structured error that tells them to formulate a budget-exhaustion
request via ``TeamSay(to=momo, ...)``.

Design constraints:
  - Does NOT modify ``agentscope/`` source -- purely a middleware.
  - Does NOT modify ``TeamSay.__call__()`` -- intercepts at the acting hook.
  - Task-to-task budget isolation: each task has its own budget counter.
  - ``TeamSay(to=momo)`` is always free (never deducts budget).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator

from agentscope.middleware import MiddlewareBase
from agentscope.message import TextBlock, ToolResultState
from agentscope.tool import ToolChunk

from .logging import get_logger

if TYPE_CHECKING:
    from agentscope.agent import Agent
    from agentscope.message import ToolCallBlock

log = get_logger(__name__)

# ── AgentScope on_acting hook introspection ─────────────
# _agent.py:1569-1579 — the call site:
#   input_kwargs = {"tool_call": tool_call_block}
#   async for item in mw.on_acting(
#       agent=self,
#       input_kwargs=input_kwargs,    # dict with 1 key
#       next_handler=next_handler,     # callable(**kwargs) → execute_chain
#   ):
#
# next_handler expects: next_handler(tool_call=tool_call_block)
# ToolCallBlock has .name (tool name) and .input (tool params dict).


class CommunicationBudgetMiddleware(MiddlewareBase):
    """Middleware that enforces the communication_budget per task.

    Attached as an ``on_acting`` hook.  When the agent calls any tool,
    we check whether it is TeamSay(to=<peer>) -- if so, deduct budget
    from the caller's highest-budget active task.

    Must be constructed with a reference to the project's DashboardDAO
    so it can read + update task budgets at runtime.
    """

    def __init__(
        self,
        dashboard_dao,
        agent_id: str,
        window_id: str,
        momo_id: str = "",
    ) -> None:
        self._dao = dashboard_dao
        self._agent_id = agent_id
        self._window_id = window_id
        self._momo_id = momo_id

    def _is_leader(self, to: str) -> bool:
        """Return True if ``to`` name matches momo_id (leader)."""
        return bool(self._momo_id) and to == self._momo_id

    # ── AgentScope on_acting hook ──────────────────────

    async def on_acting(
        self,
        agent: "Agent",
        input_kwargs: dict,
        next_handler,
    ) -> AsyncGenerator["ToolChunk | ToolResponse", None]:
        """Intercept tool calls before execution.

        Only acts on ``TeamSay`` calls targeting a peer.  Everything else
        passes through unmodified.

        Args:
            agent: The Agent instance executing this middleware.
            input_kwargs: dict with single key ``"tool_call"`` →
                ``ToolCallBlock`` (already validated + permitted).
            next_handler: callable(**kwargs) that invokes the next
                middleware or ``_acting_impl``.  Accepts
                ``tool_call=ToolCallBlock``.
        """
        tool_call: "ToolCallBlock" = input_kwargs["tool_call"]
        tool_name = tool_call.name
        tool_input: dict[str, Any] = tool_call.input or {}

        # -- Only intercept TeamSay ------------------------------------------
        if tool_name != "TeamSay":
            async for event in next_handler(tool_call=tool_call):
                yield event
            return

        # -- Resolve direction ------------------------------------------------
        to = tool_input.get("to")
        if to == self._agent_id:
            # Self-targeting — TeamSay blocks this itself, pass through.
            async for event in next_handler(tool_call=tool_call):
                yield event
            return
        if to is not None and self._is_leader(to):
            # Sending to momo (leader) — always free.
            log.debug("Budget: %s→momo (free)", self._agent_id)
            async for event in next_handler(tool_call=tool_call):
                yield event
            return
        # to is None (broadcast) or to is a peer name — apply budget.

        # -- Find active task with remaining budget ---------------------------
        active_tasks = self._dao.get_tasks_for_agent(
            self._agent_id, self._window_id,
        )
        in_progress = [t for t in active_tasks if t.status == "in_progress"]

        if not in_progress:
            # No active task — let through.  The LLM might be asking momo
            # for a task; TeamSay's own resolution handles routing.
            async for event in next_handler(tool_call=tool_call):
                yield event
            return

        # Pick the task with the highest remaining budget
        best_task = max(in_progress, key=lambda t: t.communication_budget)

        if best_task.communication_budget <= 0:
            # -- Budget exhausted ---------------------------------------------
            budget_exhausted_msg = (
                f"[通信预算耗尽] 你在任务 '{best_task.title}' ({best_task.id}) "
                f"上的 communication_budget 已用完。\n\n"
                f"请通过 TeamSay(to=momo, ...) 向 momo 发送预算耗尽申请，说明：\n"
                f"  1. 你在执行哪个任务时遇到了什么需要确认的问题\n"
                f"  2. 为什么需要继续与同事通信\n"
                f"  3. 申请增加预算，或由 momo 协调处理"
                f"（比如任务设计不合理、需求不明确等）\n\n"
                f"momo 会评估情况并决定：增加 budget、拆分任务、或亲自介入协调。"
            )
            yield ToolChunk(
                content=[TextBlock(text=budget_exhausted_msg)],
                state=ToolResultState.ERROR,
            )
            return

        # -- Deduct budget ----------------------------------------------------
        new_budget = best_task.communication_budget - 1
        self._dao.update_task(best_task.id, communication_budget=new_budget)
        log.info(
            "Budget: agent=%s task=%s budget %d→%d peer=%s",
            self._agent_id,
            best_task.id[:12],
            best_task.communication_budget,
            new_budget,
            to or "(broadcast)",
        )

        # Let the tool call proceed unmodified
        async for event in next_handler(tool_call=tool_call):
            yield event

# Original Design Proposal — Issue #1422

- **URL:** https://github.com/agentscope-ai/agentscope/issues/1422
- **Retrieved:** 2025-07-14

---

## Background
Complex tasks often benefit from parallel execution by multiple specialized agents. AgentScope currently lacks a structured mechanism for coordinating such workflows.

## Proposed Changes
Introduce team-mode collaboration, where:
- The primary agent publishes tasks to a shared task queue
- Sub-agents subscribe to, claim, and complete tasks asynchronously
- Results are submitted back to a global queue for aggregation
- Tool locking mechanisms will be introduced to prevent conflicts when multiple agents access shared resources.

## Status
Closed — implemented by PR #1776

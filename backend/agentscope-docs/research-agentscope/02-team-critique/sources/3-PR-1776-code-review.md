# PR #1776 — Implementation Code Review

- **URL:** https://github.com/agentscope-ai/agentscope/pull/1776
- **Retrieved:** 2025-07-14

---

## Stats
- 12 commits, 154 files changed, +12016 / -2425 lines
- Merged: Jun 5, 2026

## Key Source Files

### _team_create.py
- Creates TeamRecord with session_id = caller's session (hard-coded as leader)
- Checks session.team_id is None (one team per session constraint)
- TeamData has: name, description, member_ids (list of agent ids)

### _agent_create.py
- Only callable by team leader (checks team.session_id == self._session_id)
- Builds AgentRecord(source="team") — hidden from global agent list
- Builds system prompt dynamically from team name/desc and member name/desc
- Creates new SessionRecord inheriting leader's model config and workspace
- Appends agent_id to team.data.member_ids
- Delivers initial prompt to worker via message bus inbox + wakeup
- Worker starts executing immediately

### _team_say.py
- Routes by name (not agent_id) via directory built from team membership
- Both leader and workers can call TeamSay
- Workers see a different description (leader-focused vs broadcast-focused)
- Broadcast sends to all members except self
- Name uniqueness enforced at AgentCreate time

### _inbox_middleware.py
- Drains inbox at start of each reasoning step
- Injects HintBlocks into agent.state.context
- Yields HintBlockEvent for front-end SSE rendering

### TeamRecord (storage model)
- user_id, session_id (leader), data: {name, description, member_ids: list[str]}
- member_ids stores agent_ids of workers (1:1 agent to session mapping)

### AgentRecord (storage model)
- source: Literal["user", "team"] = "user"
- "team" agents hidden from list_agents (filtered in RedisStorage.list_agents)

### Original Design vs Implementation Gap
Original issue #1422 proposed:
- Shared task queue for publish/subscribe
- Sub-agents claim tasks asynchronously
- Global result aggregation queue
- Tool locking for shared resource access

Actually implemented:
- Leader-driven create-and-coordinate
- Star topology via TeamSay
- No shared queue, no task claiming
- No tool locking

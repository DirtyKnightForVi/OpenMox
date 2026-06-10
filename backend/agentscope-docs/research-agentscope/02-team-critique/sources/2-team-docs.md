# Agent Team Docs — 智能体团队

- **URL:** https://docs.agentscope.io/zh/v2/deploy/agent-team
- **Retrieved:** 2025-07-14

---

## Core Concept
Leader 智能体通过内置 team 工具派生并协调 worker 智能体。

智能体团队是构建在智能体服务之上的多智能体层。Leader 智能体可以按需派生 worker 智能体并与之交换消息，每个成员拥有独立状态、工作区绑定与事件流。整套协调能力通过四个内置工具表达，而非借助一套独立的编排框架。

## Four Built-in Tools
| Tool | Purpose | Available To |
|------|---------|-------------|
| TeamCreate | Create new team, caller becomes leader | Leader |
| AgentCreate | Spawn a new worker | Leader |
| TeamSay | Send message to member or broadcast | All |
| TeamDelete | Dissolve team and clean up | Leader |

## Team Communication Model
1. Sender's tool call pushes HintBlock to recipient's inbox via message bus
2. A wakeup signal is enqueued for the recipient
3. Wakeup dispatcher picks it up and drives ChatService.run
4. InboxMiddleware drains the inbox before the next reasoning step

## Key Properties
- Workers run CONCURRENTLY, not as nested co-routines under the leader
- Leader observes progress by reading the worker's session event stream
- Workers inherit the leader's chat model + workspace context
- Team communication reuses the same inbox + wakeup primitives used for scheduling and background tasks

# Agent Service Docs — 智能体服务

- **URL:** https://docs.agentscope.io/zh/v2/deploy/agent-service
- **Retrieved:** 2025-07-14

---

## Capabilities
| Capability | Description |
|-----------|-------------|
| Agent Team | Leader derives workers, coordinates via built-in team tools |
| Workspace Management | Pluggable isolation strategies (per-agent built-in) |
| Background Task Offloading | Long tool calls offloaded to background |
| Cron Scheduling | Time-triggered agent execution |
| Session Replay | Late-joining clients receive buffered history |
| Protocol Adaptation | Middleware converts native event stream to external protocols (AG-UI, A2A) |
| Distributed Deployment WIP | All shared state in Redis; multiple workers/nodes can serve same logical service |

## Architecture
- FastAPI-based multi-tenant, multi-session HTTP service
- Redis for storage + message bus
- Workspace managers (Local/Docker/E2B)
- Middleware pipeline for agent execution
- SessionManager, SchedulerManager, BackgroundTaskManager, WakeupDispatcher

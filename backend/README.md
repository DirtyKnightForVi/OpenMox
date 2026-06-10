# OpenMox Backend

Enterprise Multi-Agent Collaborative Platform — Python backend based on AgentScope 2.0.

## Architecture

```
main.py  →  src/  →  agentscope/ (local source, not pip package)
```

- **`main.py`** — FastAPI application entry point
- **`src/`** — Business logic (agent config, orchestration, API)
- **`agentscope/`** — AgentScope 2.0 source code (read-only, treated as project-local dependency)
- **`agents/`** — Agent YAML configuration files

## Quick Start

```bash
cd backend

# Install dependencies (Python 3.12, agentscope deps but NOT agentscope itself)
uv sync

# Set your API key
export DEEPSEEK_API_KEY="sk-..."

# Start the server
uv run python run.py
```

Server starts at **http://localhost:8000** with:
- REST API docs at http://localhost:8000/docs
- WebSocket at `ws://localhost:8000/ws`

## Key Design Decisions

### agentscope as local source (not pip package)

`backend/agentscope/` contains the full AgentScope 2.0 source code. It is **not** installed as a pip package. Instead, `run.py` adds `agentscope/src/` to `sys.path` at startup. This means:

1. **CodeGraph can trace every reference** from `src/` into `agentscope/` — no black-box dependencies
2. **Zero modifications** to agentscope source
3. **Easy to upgrade** — just `git pull` in the agentscope directory

### Storage

- **SQLite** (`data/openmox.db`) — projects, sessions, messages
- Redis not required (unlike AgentScope's built-in Agent Service)

### API Protocol

The backend speaks the PilotDeck V2 protocol for frontend compatibility:
- REST: `/api/agents`, `/api/projects`, `/api/sessions`, `/api/config`
- WebSocket: `/ws` — `pilotdeck-command` messages with `@agentId` mention routing

## Module Map

```
src/
├── core/
│   ├── settings.py       # Environment variables
│   ├── logging.py        # Structured logging with trace-id
│   ├── store.py          # SQLite persistence (aiosqlite)
│   └── agent_factory.py  # AgentScope model/agent singletons
├── agent_config/
│   └── manager.py        # YAML agent config CRUD
├── orchestration/
│   ├── router.py         # @mention parser
│   └── fanout.py         # Multi-agent concurrent streaming
├── api/
│   ├── router.py         # Unified route registration
│   ├── agents.py         # Agent CRUD endpoints
│   ├── projects.py       # Project CRUD endpoints
│   ├── sessions.py       # Session management endpoints
│   ├── config.py         # Config/settings endpoints
│   └── chat.py           # WebSocket chat handler (core)
├── memory/               # Phase 2: White-box Memory
└── permission/           # Phase 2: Four-layer file permissions
```

## Data Flow

```
Frontend (WebSocket /ws)
  → {"type":"pilotdeck-command", "command":"@pm @dev 分析需求"}
  → MentionRouter.parse() → ["pm", "dev"], "分析需求"
  → FanoutStreamer.stream()
      → Agent(agent_id="pm", system_prompt=...).reply_stream()
      → Agent(agent_id="dev", system_prompt=...).reply_stream()
      (concurrent via asyncio.gather)
  → Events tagged with _agent_id streamed to frontend
  → Messages persisted to SQLite
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | (required) | DeepSeek API key |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | API base URL |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | Model name |

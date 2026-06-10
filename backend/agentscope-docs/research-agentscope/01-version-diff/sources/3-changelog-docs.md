# Changelog - AgentScope Docs (v2 vs v1)

- **URL:** https://docs.agentscope.io/zh/v2/change-log
- **Retrieved:** 2025-07-14

---

This changelog primarily describes the differences between AgentScope 2.0 (base) and 1.0. It is a breaking update.

Key module-level differences:
- Agent: ReActAgent → new Agent class, reply_stream/reply replaces __call__, event stream for permission and human-in-the-loop, Offloader for context compression, hooks deprecated → middleware
- Event: New event system for frontend integration and human-in-the-loop
- Message: Content block refactored to Pydantic BaseModel, ImageBlock/AudioBlock/VideoBlock → unified DataBlock, new HintBlock, ToolUseBlock → ToolCallBlock, Msg refactored with created_at/finished_at/usage, new UserMsg/AssistantMsg/SystemMsg factories
- Permission: New permission system for tool execution gating
- Tool: New ToolBase abstract, builtin tools (Bash, Edit, Glob, Grep, Read, Write, TaskCreate/Get/List/Update), Toolkit refactored with ToolGroup support, ResetTools meta-tool, MCPTool and FunctionTool adapters
- MCP: Unified MCPClient class, StdioMCPConfig and HttpMCPConfig
- Skill: New skill loader, LocalSkillLoader, skill as ToolGroup
- Workspace: New abstraction, LocalWorkspace/DockerWorkspace/E2BWorkspace, Offloader protocol, MCP gateway in workspace
- Model: Credential management decoupled, Kimi/Moonshot/DeepSeek/XAI/OpenAI Response API support, formatter integrated into chat model, ModelCard, list_models
- Middleware: Hook → middleware system, TracingMiddleware
- Agent Service: FastAPI-based, create_app factory, SessionManager/SchedulerManager/BackgroundTaskManager, AGUIProtocolMiddleware, ToolOffloadMiddleware, Redis storage backend
- Memory: Deprecated in 2.0
- RAG & Long-Term Memory: Unified under single module, migration in progress

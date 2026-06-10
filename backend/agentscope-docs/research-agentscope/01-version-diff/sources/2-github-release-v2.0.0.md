# v2.0.0 Release Notes

- **URL:** https://github.com/agentscope-ai/agentscope/releases/tag/v2.0.0
- **Retrieved:** 2025-07-14

---

## v2.0.0

Released: 25 May 15:44

### AgentScope 2.0 is released!
Please refer to the new docs for more information.

### What's Changed
- chore(project): temporarily deprecate evaluate/module/rag/tts/realtime modules pending refactor by @DavdGao
- refactor(msg): simplify core building blocks and Msg class structure by @DavdGao
- feat(msg): formalize Msg type rules and constraints and add message related tests by @DavdGao
- feat(permission): build the basic permission classes by @DavdGao
- refactor(tool): refactor the tool module, including providing new base class and toolkit logic by @DavdGao
- ci(mcp): refactor the previous MCP unittests for the new version by @DavdGao
- feat(tool): implement builtin tools with ToolBase inheritance and add comprehensive tests by @DavdGao
- refactor(skill): refactor the skill in the toolkit by adding a new skill loader class by @DavdGao
- feat(agent): implement permission checking logic within the agent class by @DavdGao
- feat(context): support context compression in Agent class by @DavdGao
- feat(task): add task related tools in agentscope 2.0 by @DavdGao
- refactor(mcp): rename the mcp when registered into the toolkit by @DavdGao
- refactor(mcp): unify the MCP implementation into a MCPClient class by @DavdGao
- feat(middleware): support 2.0 middlewares in the agent class by @DavdGao
- feat(context): support tool result compact within the Agent class by @DavdGao
- feat(workspace): built the workspace module in agentscope 2.0 by @DavdGao
- refactor(model): refactor the chat model implementation by @DavdGao
- factor(tool): refactor the tool_choice argument by @qbc2016
- feat(scripts): add scripts for model call by @qbc2016
- feat(model): add cache_creation_input_tokens and cache_input_tokens in ChatUsage by @qbc2016
- fix(dashscope): fix KeyError in dashscope response by @qbc2016
- refactor(model): refactor dashscope model to openai compatible by @qbc2016
- refactor: rename kimi to moonshot by @qbc2016
- refactor(tracing): refactor tracing module by @qbc2016
- fix(formatter): refine formatters and unittest by @qbc2016
- feat(service): implement the FastAPI based agent service by @DavdGao
- feat(trace): add trace as a middleware by @qbc2016
- feat(model): uniform thinking tag by @qbc2016
- fix(model): refine _format_tools for openai response model by @qbc2016
- fix(scripts): assign a list of textblock to the content instead of a string by @qbc2016
- fix(mcp): preserve $defs in MCPTool input schema and strip titles recursively by @qbc2016
- feat(model): handle audio output for openai by @qbc2016
- feat(msg): add usage in msg by @qbc2016
- feat(tool): integrate the tool and workspace modules with the Agent class by @DavdGao
- feat(model): fix dashscope structured output and add examples by @qbc2016
- fix(formatter): download remote image URLs to base64 for Moonshot by @qbc2016
- fix(tool): close .env bypass gap and refine dangerous-path API for Write/Edit/Bash by @qbc2016
- refactor(workspace): support e2b and docker workspace, as well as their managers by @DavdGao
- docs(readme): update the docs for 2.0 release by @DavdGao
- chore(version): update the version to 2.0.0 and release to PyPI by @DavdGao

### Full Changelog
v1.0.21...v2.0.0

### Contributors
@qbc2016, @DavdGao

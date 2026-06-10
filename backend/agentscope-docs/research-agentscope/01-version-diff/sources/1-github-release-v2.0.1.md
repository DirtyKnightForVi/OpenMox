# v2.0.1 Release Notes

- **URL:** https://github.com/agentscope-ai/agentscope/releases/tag/v2.0.1
- **Retrieved:** 2025-07-14

---

## v2.0.1

Released: 05 Jun 12:13

### Highlight
- **Agent Team** is supported

### What's Changed
- fix(webui): add missing files in the web ui example by @DavdGao in #1661
- fix(readme): update the QR code for DingTalk group by @DavdGao in #1662
- perf(service): support to provide extra tools and middlewares by @DavdGao in #1709
- fix(formatter): drop thinking blocks without signature for Anthropic by @qbc2016 in #1668
- feat(webui): support to set fallback model in web UI by @DavdGao in #1699
- feat(model): add client_kwargs in model by @qbc2016 in #1659
- feat(model): add yaml configs for mainstream models by @MannXo in #1731
- feat(rag): add the basic class for the RAG module by @DavdGao in #1746
- fix(model): refine retry logic by @qbc2016 in #1730
- fix(tool): support plain return values in FunctionTool by @xunx911 in #1703
- fix(tool): clean the file cache of the builtin Read tool by @googs1025 in #1735
- fix(storage): expire Redis message lists by @he-yufeng in #1734
- fix(webui): fix frontend build with current dependencies by @yuanchangsai77 in #1708
- fix(tool): hide bash subprocess windows on Windows by @he-yufeng in #1717
- fix(workspace): add locks to mcp and skill operations in LocalWorkspace by @weizhang25 in #1710
- perf(permission): improve the implementation of the current permission system by @DavdGao in #1767
- feat(agent_team): refactor the agent service to support agent team by @DavdGao in #1776
- feat(event): add metadata in EventBase by @qbc2016 in #1788
- fix(mcp): sanitize MCPTool name for LLM provider compatibility by @qbc2016 in #1787
- fix(model): honor explicit thinking_enable=False on Ollama and Gemini by @qbc2016 in #1784
- docs(readme): update readme for the new service feature by @DavdGao in #1789
- fix(webui): use asChild on Button tooltip trigger to avoid nested by @fancyboi999 in #1770
- fix(webui): add dialog descriptions for accessibility by @fancyboi999 in #1771
- fix: include tool group skills by @he-yufeng in #1732
- feat(deps): make ripgrep an optional dependency by @Oxygen56 in #1740

### New Contributors
- @MannXo, @xunx911, @googs1025, @he-yufeng, @yuanchangsai77, @fancyboi999, @Oxygen56

### Stats
- 25 commits, 251 files changed, 14 contributors

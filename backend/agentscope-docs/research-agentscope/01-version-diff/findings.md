# Research Findings: AgentScope 2.0.0 vs 2.0.1 差异分析

**日期:** 2025-07-14
**参考来源数:** 3
**输出目录:** research-agentscope-2.0-diff/

## 概述

AgentScope 2.0.0 是 2.x 系列的首个正式版本（2025年5月25日发布），是一次彻底的破坏性更新。AgentScope 2.0.1 是一个补丁/小特性版本（2025年6月5日发布），在 2.0.0 的基础上进行了 bug 修复、性能优化并引入了新功能。

## 关键发现

### 1. 版本性质差异

- **v2.0.0**: 大版本发布，包含完整的架构重构（25 May 2025）
- **v2.0.1**: 补丁发布（05 Jun 2025），距 v2.0.0 约11天，包含 **25 个 commits**、**251 个文件变动**、**14 位贡献者**
  - _Source: [GitHub Compare](https://github.com/agentscope-ai/agentscope/compare/v2.0.0...v2.0.1) — sources/1-github-release-v2.0.1.md_

### 2. 最大的新功能：Agent Team（智能体团队）

这是 v2.0.1 的 **Highlight** 特性：
- 重构了 agent service 以支持 agent team（#1776）
- 允许将多个智能体组合成一个团队协作工作
- 相关的 docs 也进行了更新（#1789）
  - _Source: [v2.0.1 Release Notes](https://github.com/agentscope-ai/agentscope/releases/tag/v2.0.1) — sources/1-github-release-v2.0.1.md_

### 3. 新增的模块级功能

在 v2.0.1 中新增的功能模块：

| 功能 | 模块 | PR | 贡献者 |
|------|------|----|--------|
| RAG 基础类 | rag | #1746 | @DavdGao |
| Web UI 回退模型 | webui | #1699 | @DavdGao |
| 模型 client_kwargs | model | #1659 | @qbc2016 |
| 主流模型 YAML 配置 | model | #1731 | @MannXo |
| EventBase 元数据 | event | #1788 | @qbc2016 |
| ripgrep 可选依赖 | deps | #1740 | @Oxygen56 |

_Source: [v2.0.1 Release Notes](https://github.com/agentscope-ai/agentscope/releases/tag/v2.0.1) — sources/1-github-release-v2.0.1.md_

### 4. Service 层改进

- **支持提供额外的 tools 和 middlewares**（#1709）- perf(service)
- 这是从 v2.0.0 的基础 agent service（FastAPI-based）上的性能增强
  - _Source: [v2.0.1 Release Notes](https://github.com/agentscope-ai/agentscope/releases/tag/v2.0.1) — sources/1-github-release-v2.0.1.md_

### 5. Permission 系统优化

- **改进当前权限系统的实现**（#1767）- perf(permission)
- v2.0.0 首次引入了权限系统（#1486），v2.0.1 对其进行了性能优化
  - _Source: [v2.0.1 Release Notes](https://github.com/agentscope-ai/agentscope/releases/tag/v2.0.1) — sources/1-github-release-v2.0.1.md_

### 6. Bug 修复清单

v2.0.1 修复了大量 bug，按模块分类：

**WebUI 修复（4项）**:
- 添加 web ui 示例中缺失的文件 (#1661)
- 修复前端构建与当前依赖的兼容性 (#1708)
- 使用 asChild 避免嵌套 button (#1770)
- 为无障碍添加 dialog 描述 (#1771)

**Model 修复（3项）**:
- 优化 Anthropic formatter 的 thinking 块处理 (#1668)
- 完善重试逻辑 (#1730)
- 修复 Ollama 和 Gemini 上 thinking_enable=False 不生效 (#1784)

**Tool 修复（3项）**:
- FunctionTool 支持纯返回值 (#1703)
- 清理内置 Read 工具的文件缓存 (#1735)
- Windows 上隐藏 bash 子进程窗口 (#1717)

**MCP 修复（1项）**:
- 对 MCPTool name 进行清理以兼容 LLM provider (#1787)

**Storage 修复（1项）**:
- Redis 消息列表添加过期时间 (#1734)

**Workspace 修复（1项）**:
- LocalWorkspace 中 mcp 和 skill 操作添加锁 (#1710)

**Skill 修复（1项）**:
- 在 get_skill_instructions 中包含 tool group skills (#1732)

_Source: [v2.0.1 Release Notes](https://github.com/agentscope-ai/agentscope/releases/tag/v2.0.1) — sources/1-github-release-v2.0.1.md_

### 7. 新贡献者

v2.0.1 引入了 **7 位新贡献者**（v2.0.0 仅 2 位），说明社区参与度在增长：
- @MannXo, @xunx911, @googs1025, @he-yufeng, @yuanchangsai77, @fancyboi999, @Oxygen56
  - _Source: [v2.0.1 Release Notes](https://github.com/agentscope-ai/agentscope/releases/tag/v2.0.1) — sources/1-github-release-v2.0.1.md_

### 8. v2.0.0 的特性（v2.0.1 继承的基础）

v2.0.0 包含了完整的架构革新，v2.0.1 在此基础上增量改进。v2.0.0 的关键特性包括：
- Agent 类重构（取代 ReActAgent）
- 全新的 Message/Event 系统
- Permission 系统
- Tool 重构（ToolBase、内置工具）
- Workspace 系统（Local/Docker/E2B）
- MCP 客户端统一
- Skill Loader
- Middleware 系统
- FastAPI 推理服务
- Model 重构（Credential 解耦、多模型支持）

## 来源汇总

| # | 来源 | URL | 关键见解 | 可信度 |
|---|------|-----|---------|--------|
| 1 | GitHub v2.0.1 Release | https://github.com/agentscope-ai/agentscope/releases/tag/v2.0.1 | 完整的发布说明、所有 PR 列表、新贡献者 | 高 |
| 2 | GitHub v2.0.0 Release | https://github.com/agentscope-ai/agentscope/releases/tag/v2.0.0 | 2.0 基础版本的完整 PR 列表 | 高 |
| 3 | GitHub Compare v2.0.0...v2.0.1 | https://github.com/agentscope-ai/agentscope/compare/v2.0.0...v2.0.1 | 25 commits, 251 files changed, 14 contributors | 高 |
| 4 | AgentScope Docs Changelog | https://docs.agentscope.io/zh/v2/change-log | 2.0 vs 1.0 的模块级差异概览 | 高 |

## 结论

**AgentScope 2.0.1 本质上是对 2.0.0 的增量改进版本**，核心策略是"稳定已有功能 + 填补能力空白"：

1. **最大亮点**：Agent Team（智能体团队）的引入，使多智能体协作成为可能
2. **填补空白**：RAG 模块的基础类开始搭建，为后续的文档问答等能力铺路
3. **稳定性提升**：修复了 2.0.0 中暴露的大量 bug（至少 13 项修复），覆盖 WebUI、Model、Tool、MCP、Storage、Workspace、Skill 等多个模块
4. **性能优化**：Service 层和 Permission 系统得到了性能增强
5. **开发者体验**：新增主流模型的 YAML 配置、client_kwargs、Web UI 回退模型等便利功能
6. **社区增长**：7 位新贡献者表明开源社区正在积极参与

**建议**：如果已经在使用 2.0.0，强烈建议升级到 2.0.1，尤其是需要 Agent Team 功能或遇到了 2.0.0 中的 bug 的情况。

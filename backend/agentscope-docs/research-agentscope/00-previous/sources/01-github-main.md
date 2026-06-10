# AgentScope GitHub 主仓库

- **URL:** https://github.com/agentscope-ai/agentscope
- **Retrieved:** 2025-01-XX

---

## AgentScope 简介

AgentScope 是阿里巴巴通义实验室开源的生产级多智能体框架，设计用于构建、编排和部署基于LLM的应用程序。

### 核心特点

1. **生产就绪** - 企业级开箱即用的智能体框架
2. **模型微调支持** - 内置对模型微调的支持
3. **自解释API** - 灵活的编程接口
4. **多智能体协作** - 支持复杂的多智能体交互

### 主要仓库

- **AgentScope (Python):** 主要的框架仓库
- **AgentScope-Runtime:** 用于可扩展部署的运行时环境
- **AgentScope-Samples:** 示例代码集合

### 安装要求

```bash
pip install agentscope[full]
```

- Python 3.10+
- 支持OpenAI API或兼容的模型配置

### 核心概念

1. **Agent** - 智能体基本单元
2. **Message (Msg)** - 消息传递机制
3. **Pipeline** - 工作流管道
4. **MsgHub** - 消息中心（聊天室）
5. **Memory** - 记忆系统
6. **Tool** - 工具调用

### 目录结构

```
examples/
├── agent/           # Agent示例
├── deployment/      # 部署示例
├── evaluation/      # 评估示例
├── functionality/   # 功能示例
├── game/            # 游戏示例（狼人杀）
├── integration/     # 集成示例
├── tuner/           # 调优示例
└── workflows/       # 工作流示例
    ├── multiagent_concurrent/    # 并发多智能体
    ├── multiagent_conversation/  # 多智能体对话
    ├── multiagent_debate/        # 多智能体辩论
    └── multiagent_realtime/      # 实时多智能体
```

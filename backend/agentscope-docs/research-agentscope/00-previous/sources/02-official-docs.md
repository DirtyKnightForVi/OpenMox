# AgentScope 官方文档

- **URL:** https://doc.agentscope.io
- **Retrieved:** 2025-01-XX

---

## 多智能体工作流教程

### 1. Conversation（对话）
多智能体之间的基本对话模式。

### 2. Multi-Agent Debate（多智能体辩论）
实现多轮讨论工作流，多个solver和aggregator之间的辩论。

**关键组件：**
- Debater Agents (Alice, Bob)
- Moderator Agent (Aggregator)
- MsgHub - 广播消息
- 结构化输出 (JudgeModel)

### 3. Concurrent Agents（并发智能体）
使用 `asyncio.gather` 并发执行多个agent。

```python
import asyncio

async def run_concurrent_agents():
    agent1 = ExampleAgent("Agent 1")
    agent2 = ExampleAgent("Agent 2")
    await asyncio.gather(agent1(), agent2())
```

### 4. Routing（路由）
动态路由消息到不同的agent。

### 5. Handoffs（交接）
Orchestrator-Workers 工作流模式，通过工具调用来动态创建工作线程。

**核心概念：**
- Orchestrator (协调器) - 决定任务如何分配
- Workers (工作者) - 执行具体任务
- 工具调用实现任务切换

## 其他关键特性

- **Pipeline** - sequential_pipeline, fanout_pipeline 等
- **MsgHub** - 消息中心，实现agent间消息广播
- **Memory** - InMemoryMemory, Long-Term Memory
- **Tool** - 工具调用和Toolkit
- **A2A Protocol** - Agent-to-Agent 协议，用于生产部署
- **Realtime Agent** - 实时语音交互
- **RAG** - 检索增强生成
- **AgentScope Studio** - 可视化工具

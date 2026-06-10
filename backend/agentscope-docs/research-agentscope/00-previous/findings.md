# AgentScope 多智能体调用研究报告

**日期:** 2025年1月
**研究主题:** AgentScope (Python版) 多智能体调用Demo
**来源数量:** 8个核心来源

---

## 执行摘要

AgentScope 是阿里巴巴通义实验室开源的企业级多智能体框架，专为应用开发者设计。框架提供了丰富的多智能体调用模式和完整的示例代码，包括对话、辩论、并发执行、游戏模拟、金融交易等场景。

**核心发现：**
1. ✅ 提供多种多智能体工作流模式（Conversation、Debate、Concurrent、Handoffs）
2. ✅ 丰富的开源示例（狼人杀、交易系统、深度研究等）
3. ✅ 支持长期记忆、工具调用、语音交互等高级特性
4. ✅ 完善的官方文档和教程

---

## 一、多智能体Demo汇总

### 1.1 官方示例 (agentscope/examples/workflows/)

| Demo名称 | 文件路径 | 描述 | 复杂度 |
|---------|---------|------|-------|
| Multi-Agent Conversation | `multiagent_conversation/main.py` | 基础对话，使用MsgHub | ⭐⭐ |
| Multi-Agent Debate | `multiagent_debate/main.py` | 辩论工作流，结构化输出 | ⭐⭐⭐ |
| Multi-Agent Concurrent | `multiagent_concurrent/main.py` | 并发执行，fanout pipeline | ⭐⭐ |
| Multi-Agent Realtime | `multiagent_realtime/` | 实时语音多智能体交互 | ⭐⭐⭐⭐ |

### 1.2 Sample仓库示例 (agentscope-samples/)

| Demo名称 | 文件路径 | 描述 | 复杂度 |
|---------|---------|------|-------|
| EvoTraders | `evotraders/` | 6角色金融交易团队 | ⭐⭐⭐⭐⭐ |
| Werewolf Game | `games/game_werewolves/` | 9人狼人杀游戏 | ⭐⭐⭐⭐ |
| Deep Research | `deep_research/` | 深度研究智能体 | ⭐⭐⭐⭐ |
| Conversational Agents | `conversational_agents/` | 多种对话场景 | ⭐⭐⭐ |
| Browser Use | `browser_use/` | 浏览器自动化 | ⭐⭐⭐ |

---

## 二、核心多智能体模式详解

### 2.1 MsgHub 消息中心模式

**用途:** 创建聊天室，让多个agent共享消息上下文

```python
async with MsgHub(participants=[agent1, agent2, agent3]) as hub:
    await agent1()  # agent2和agent3会自动收到消息
    await agent2()  # agent1和agent3会自动收到消息
```

**适用场景:**
- 群聊对话
- 团队讨论
- 信息同步

### 2.2 Pipeline 管道模式

**顺序执行:**
```python
from agentscope.pipeline import sequential_pipeline
await sequential_pipeline([agent1, agent2, agent3])
```

**并发执行:**
```python
from agentscope.pipeline import fanout_pipeline
results = await fanout_pipeline([agent1, agent2, agent3], enable_gather=True)
```

**适用场景:**
- 工作流编排
- Map-Reduce计算
- 并行分析

### 2.3 Debate 辩论模式

**特点:**
- 多轮对话
- 结构化输出判断
- 主持人协调

**核心逻辑:**
```python
while True:
    async with MsgHub(participants=[alice, bob, moderator]):
        await alice(msg)
        await bob(msg)
    
    # 主持人判断结果
    judge_result = await moderator(msg, structured_model=JudgeModel)
    if judge_result.metadata.get("finished"):
        break
```

### 2.4 Handoffs 工作交接模式

**用途:** Orchestrator动态创建Workers处理子任务

**流程:**
1. Orchestrator分析任务
2. 调用 `create_worker` 工具创建worker
3. Worker执行任务
4. 结果返回给Orchestrator

**适用场景:**
- 复杂任务分解
- 多领域协作
- 动态资源分配

### 2.5 并发执行模式

**方式1: asyncio.gather**
```python
await asyncio.gather(agent1(), agent2(), agent3())
```

**方式2: fanout_pipeline**
```python
results = await fanout_pipeline(agents=[agent1, agent2, agent3])
```

---

## 三、经典完整Demo代码

### 3.1 最简多智能体对话 (推荐入门)

文件: `examples/workflows/multiagent_conversation/main.py`

```python
import asyncio
import os
from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeMultiAgentFormatter
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.pipeline import MsgHub, sequential_pipeline

def create_participant_agent(name: str, age: int, career: str, character: str):
    return ReActAgent(
        name=name,
        sys_prompt=f"You're a {age}-year-old {career} named {name}.",
        model=DashScopeChatModel(
            model_name="qwen-max",
            api_key=os.environ["DASHSCOPE_API_KEY"],
        ),
        formatter=DashScopeMultiAgentFormatter(),
    )

async def main():
    alice = create_participant_agent("Alice", 30, "teacher", "friendly")
    bob = create_participant_agent("Bob", 14, "student", "rebellious")
    charlie = create_participant_agent("Charlie", 28, "doctor", "thoughtful")

    async with MsgHub(participants=[alice, bob, charlie]) as hub:
        await sequential_pipeline([alice, bob, charlie])

asyncio.run(main())
```

### 3.2 多智能体辩论 (结构化输出)

文件: `examples/workflows/multiagent_debate/main.py`

```python
from pydantic import BaseModel, Field
from agentscope.pipeline import MsgHub

class JudgeModel(BaseModel):
    finished: bool = Field(description="Whether the debate is finished.")
    correct_answer: str | None = Field(default=None)

async def run_debate():
    async with MsgHub(participants=[alice, bob, moderator]):
        await alice(msg)
        await bob(msg)
    
    result = await moderator(msg, structured_model=JudgeModel)
```

### 3.3 贸易分析团队 (企业级应用)

文件: `agentscope-samples/evotraders/backend/main.py`

6个角色的金融交易团队架构：
```
┌─────────────────────────────────────┐
│         Portfolio Manager           │
│          (投资决策)                  │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│     ┌─────────┐   ┌─────────┐      │
│     │ Analyst │   │ Analyst │      │
│     │(Fund.)  │   │(Tech.)  │      │
│     └─────────┘   └─────────┘      │
│     ┌─────────┐   ┌─────────┐      │
│     │ Analyst │   │ Analyst │      │
│     │(Sent.)  │   │(Val.)   │      │
│     └─────────┘   └─────────┘      │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│        Risk Manager                 │
│        (风险控制)                    │
└─────────────────────────────────────┘
```

---

## 四、关键技术特性

### 4.1 Agent类型

| Agent类型 | 说明 | 示例 |
|-----------|------|------|
| ReActAgent | 推理+行动智能体 | 最常用 |
| DialogAgent | 对话智能体 | 简单对话 |
| UserAgent | 用户输入代理 | 获取用户输入 |

### 4.2 关键组件

| 组件 | 功能 |
|------|------|
| MsgHub | 消息广播中心 |
| Pipeline | 工作流管道 |
| Memory | 记忆系统 (InMemoryMemory, ReMeLongTermMemory) |
| Toolkit | 工具集合 |
| Session | 会话管理 |

### 4.3 模型支持

支持多种模型后端：
- DashScope (通义千问)
- OpenAI
- Anthropic
- Ollama (本地模型)
- vLLM

---

## 五、学习路径建议

### 5.1 入门路径

1. **基础安装**
   ```bash
   pip install agentscope[full]
   ```

2. **运行第一个多智能体对话**
   - 参考: `examples/workflows/multiagent_conversation/`

3. **理解MsgHub机制**
   - 这是多智能体通信的核心

### 5.2 进阶路径

1. **Debate工作流**
   - 学习结构化输出
   - 理解多轮对话控制

2. **并发执行**
   - asyncio.gather
   - fanout_pipeline

3. **添加工具调用**
   - 使用Tools增强Agent能力

### 5.3 项目级应用

1. **EvoTraders** - 学习企业级架构
2. **Werewolf Game** - 学习复杂Social交互
3. **Deep Research** - 学习研究型Agent

---

## 六、参考链接

### 官方资源

| 资源 | 链接 |
|------|------|
| 主仓库 | https://github.com/agentscope-ai/agentscope |
| 示例仓库 | https://github.com/agentscope-ai/agentscope-samples |
| 官方文档 | https://doc.agentscope.io |
| PyPI | https://pypi.org/project/agentscope |

### 核心Demo链接

| Demo | 链接 |
|------|------|
| Multi-Agent Conversation | https://github.com/agentscope-ai/agentscope/tree/main/examples/workflows/multiagent_conversation |
| Multi-Agent Debate | https://github.com/agentscope-ai/agentscope/tree/main/examples/workflows/multiagent_debate |
| Multi-Agent Concurrent | https://github.com/agentscope-ai/agentscope/tree/main/examples/workflows/multiagent_concurrent |
| Werewolf Game | https://github.com/agentscope-ai/agentscope-samples/tree/main/games/game_werewolves |
| EvoTraders | https://github.com/agentscope-ai/agentscope-samples/tree/main/evotraders |

---

## 七、结论

AgentScope 提供了丰富且实用的多智能体调用Demo，覆盖了从简单对话到复杂企业级应用的各个层次：

1. **文档完善** - 官方教程涵盖了所有多智能体模式
2. **代码丰富** - 超过10个可直接运行的多智能体示例
3. **架构清晰** - MsgHub + Pipeline 的设计简洁优雅
4. **生产就绪** - 企业级应用案例（EvoTraders）证明框架成熟度

**推荐从以下顺序学习:**
1. `multiagent_conversation` - 理解基础
2. `multiagent_debate` - 学习结构化输出
3. `evotraders` - 参考企业级架构
4. `game_werewolves` - 理解复杂交互设计

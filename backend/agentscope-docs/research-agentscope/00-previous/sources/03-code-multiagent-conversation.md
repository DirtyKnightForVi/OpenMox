# 多智能体对话示例代码

- **URL:** https://github.com/agentscope-ai/agentscope/tree/main/examples/workflows/multiagent_conversation
- **Retrieved:** 2025-01-XX

---

## 完整代码

```python
# -*- coding: utf-8 -*-
"""The example of how to construct multi-agent conversation with MsgHub and
pipeline in AgentScope."""
import asyncio
import os

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeMultiAgentFormatter
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.pipeline import MsgHub, sequential_pipeline

def create_participant_agent(
    name: str,
    age: int,
    career: str,
    character: str,
) -> ReActAgent:
    """Create a participant agent with a specific name, age, and character."""
    return ReActAgent(
        name=name,
        sys_prompt=(
            f"You're a {age}-year-old {career} named {name} and you're "
            f"a {character} person."
        ),
        model=DashScopeChatModel(
            model_name="qwen-max",
            api_key=os.environ["DASHSCOPE_API_KEY"],
            stream=True,
        ),
        # Use multiagent formatter because the multiple entities will
        # occur in the prompt of the LLM API call
        formatter=DashScopeMultiAgentFormatter(),
    )

async def main() -> None:
    """Run a multi-agent conversation workflow."""

    # Create multiple participant agents with different characteristics
    alice = create_participant_agent("Alice", 30, "teacher", "friendly")
    bob = create_participant_agent("Bob", 14, "student", "rebellious")
    charlie = create_participant_agent("Charlie", 28, "doctor", "thoughtful")

    # Create a conversation where participants introduce themselves within
    # a message hub
    async with MsgHub(
        participants=[alice, bob, charlie],
        # The greeting message will be sent to all participants at the start
        announcement=Msg(
            "system",
            "Now you meet each other with a brief self-introduction.",
            "system",
        ),
    ) as hub:
        # Quick construct a pipeline to run the conversation
        await sequential_pipeline([alice, bob, charlie])
        
        # Or by the following way:
        # await alice()
        # await bob()
        # await charlie()

        # Delete a participant agent from the hub and fake a broadcast message
        print("##### We fake Bob's departure #####")
        hub.delete(bob)
        await hub.broadcast(
            Msg(
                "bob",
                "I have to start my homework now, see you later!",
                "assistant",
            ),
        )
        await alice()
        await charlie()

asyncio.run(main())
```

## 关键要点

1. **MsgHub** - 创建消息中心，所有参与者自动接收彼此的消息
2. **sequential_pipeline** - 按顺序执行agent
3. **DashScopeMultiAgentFormatter** - 多智能体格式化器
4. **动态管理参与者** - 可以添加/删除参与者

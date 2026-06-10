# Handoffs 工作流示例

- **URL:** https://doc.agentscope.io/tutorial/workflow_handoffs.html
- **Retrieved:** 2025-01-XX

---

## 简介

Handoffs模式实现 **Orchestrator-Workers** 工作流，协调器动态分配任务给工作线程。

## 关键概念

- **Orchestrator (协调器)** - 决定任务如何分配，创建Workers
- **Workers (工作者)** - 执行具体任务
- **Tool Calls** - 通过工具调用来动态创建Worker

## 交互示例

```
Orchestrator: {
    "type": "tool_use",
    "name": "create_worker",
    "input": {
        "task_description": "Print 'Hello, World!' using Python"
    },
    "id": "call_dc88ca12680348af8c3110"
}
Worker: {
    "type": "tool_use",
    "name": "execute_python_code",
    "input": {"code": "print('Hello, World!')", "timeout": 300},
    "id": "call_f6b89489f0124aaea7d6f0"
}
system: {
    "type": "tool_result",
    "id": "call_f6b89489f0124aaea7d6f0",
    "name": "execute_python_code",
    "output": [{"type": "text", "text": "<returncode>0</returncode><stdout>Hello, World!\n</stdout>"}]
}
Worker: The Python code has successfully printed 'Hello, World!'...
system: {
    "type": "tool_result",
    "id": "call_dc88ca12680348af8c3110",
    "name": "create_worker",
    "output": [{"type": "text", "text": "The Python code has successfully printed..."}]
}
Orchestrator: The worker has executed the Python code...
```

## 代码示例

```python
import asyncio
import os

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.tool import ToolResponse, Toolkit, execute_python_code

# The tool function to create a worker
async def create_worker(task_description: str) -> ToolResponse:
    """Create a worker agent to handle a specific task.
    
    The worker will be given the task description and execute the task.
    """
    # Create a new worker agent dynamically
    worker = ReActAgent(
        name="Worker",
        sys_prompt=f"You are a worker agent. Your task is: {task_description}",
        model=DashScopeChatModel(...),
        tools=Toolkit([execute_python_code]),
    )
    
    # Execute the task
    result = await worker(Msg("user", "Please complete the task.", "user"))
    
    return ToolResponse(
        text=f"Task completed with result: {result.content}"
    )

async def main():
    # Create orchestrator agent
    orchestrator = ReActAgent(
        name="Orchestrator",
        sys_prompt="""You are an orchestrator agent.
        
You can create worker agents to handle specific tasks by calling
the `create_worker` function with a task description.

Analyze the user's request and break it down into subtasks if needed.
Then create workers to handle each subtask.
""",
        model=DashScopeChatModel(...),
        tools=Toolkit([create_worker]),
    )
    
    # Run the orchestrator
    msg = Msg("user", "I need to print 'Hello, World!' in Python", "user")
    await orchestrator(msg)

asyncio.run(main())
```

## 适用场景

1. **任务分解** - 复杂任务自动分解给不同的workers
2. **动态资源分配** - 根据需要创建/销毁workers
3. **多领域协作** - 不同专业领域的agents协作
4. **Map-Reduce模式** - 任务分发-结果聚合

> ## Documentation Index
> Fetch the complete documentation index at: https://docs.agentscope.io/llms.txt
> Use this file to discover all available pages before exploring further.

# 智能体团队

> Leader 智能体通过内置 team 工具派生并协调 worker 智能体

智能体团队（Agent Team）是构建在[智能体服务](/zh/v2/deploy/agent-service)之上的多智能体层。Leader 智能体 —— 即用户对话的那个会话 —— 可以按需派生 worker 智能体并与之交换消息，而每个成员都只是另一个拥有独立状态、工作区绑定与事件流的会话。整套协调能力通过四个内置工具表达，而非借助一套独立的编排框架。

## 快速上手

随仓库附带的 [`examples/agent_service`](https://github.com/agentscope-ai/agentscope/tree/main/examples/agent_service) 后端默认启用了 team 工具，配套的 [`examples/web_ui`](https://github.com/agentscope-ai/agentscope/tree/main/examples/web_ui) 前端开箱即可渲染团队成员关系与各 worker 的事件流。按照[智能体服务快速上手](/zh/v2/deploy/agent-service#试用示例)启动两者 —— 跑起来后让 leader 智能体组建一个团队，你会看到它自动调用 `TeamCreate` / `AgentCreate`，观察 worker 上线，并在 UI 中看到它们互相交换消息。

<Frame caption="在示例 Web UI 中，leader 智能体组建团队并协调 worker。">
  <img src="https://mintcdn.com/agentscope-ai-786677c7/c8Op3M8_8-WXpeVH/images/team.gif?s=604f394f94cca0dbca8fdeee75a0f7ff" alt="智能体团队协作演示" width="1920" height="1080" data-path="images/team.gif" />
</Frame>

## 概念

| 概念                     | 说明                                                                                               |
| ---------------------- | ------------------------------------------------------------------------------------------------ |
| **团队（Team）**           | 由单个用户拥有的一组持久化智能体成员。`TeamRecord` 承载团队身份（名称、描述）及其成员列表。                                             |
| **Leader**             | 创建团队的会话。只有 leader 可以添加 / 移除成员或解散团队。                                                              |
| **Worker**             | 作为团队成员被派生出的会话。Worker 在自己的会话中运行自己的 ReAct 循环，并继承 leader 的聊天模型 + 工作区上下文。                            |
| **团队消息（Team Message）** | 通过消息总线在成员之间路由的消息。以 `HintBlock` 形式投递，外层包裹 `<team-message from="…">` 标签，让接收方的 LLM 能将其与普通的用户对话轮区分开。 |

## 内置工具

Leader 会话自动获得下列工具。Worker 只能看到 `TeamSay`。

| 工具            | 用途                                                      |
| ------------- | ------------------------------------------------------- |
| `TeamCreate`  | 以当前会话为根创建一个新团队，并成为其 leader。                             |
| `AgentCreate` | 向团队中派生一个新的 worker，附带名称、角色描述、首个任务与权限模式。Worker 创建后立即开始执行。 |
| `TeamSay`     | 向指定成员发送消息（或广播）。接收方会话通过其收件箱接收消息，并在下一次唤醒时恢复运行。            |
| `TeamDelete`  | 解散团队并清理所有成员会话。只有 leader 可调用。                            |

## 协调模型

智能体团队天然为分布式部署而设计。所有成员间的通信都由[消息总线](/zh/v2/deploy/agent-service#资源模型)居中转发 —— 一个由 Redis 支撑的抽象 —— 因此 leader 与 worker 会话可以位于不同进程或不同节点，无需任何代码改动。发送方将消息写入接收方的收件箱；集群中任意 wakeup dispatcher 都可以认领该唤醒信号，并在自己的进程上驱动该会话运行。这与支撑调度触发、后台工具完成的机制是同一套，也是为什么团队功能能与服务的其他部分一样横向扩展。

团队通信复用了服务用于调度触发与后台工具完成的同一组 inbox + wakeup 原语：

1. 发送方的工具调用（`TeamSay`、`AgentCreate` 的初始提示等）通过消息总线把 `HintBlock` 推到接收方会话的收件箱。
2. 为接收方入队一个唤醒信号。
3. 任意进程上运行的 wakeup dispatcher 取走该唤醒，并为该会话驱动 `ChatService.run`。
4. `InboxMiddleware` 在下一次推理步骤前清空收件箱，因此排队的团队消息会以 `HintBlockEvent` 的形式落入接收方上下文。

这意味着 worker 在同一服务中*并发*运行 —— 它们不是嵌套在 leader 之下的协程。Leader 通过读取 worker 的会话事件流，或让 worker `TeamSay` 回报，来观察其进展。

## 延伸阅读

<CardGroup cols={2}>
  <Card title="Agent service" icon="server" href="/zh/v2/deploy/agent-service">
    支撑团队的托管层 —— 会话、消息总线、工作区生命周期。
  </Card>

  <Card title="Agent" icon="robot" href="/zh/v2/building-blocks/agent">
    每个团队成员所运行的智能体抽象。
  </Card>
</CardGroup>


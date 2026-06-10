# Research Findings: AgentScope 2.0.1 Team Mode — 批判性分析

**日期:** 2025-07-14
**参考来源数:** 4
**输出目录:** research-agentscope-team-critique/

## 概述

本文对 AgentScope 2.0.1 的 Agent Team 功能进行全面批判性评估，分析其设计优劣，并与用户期望的"声明式组队"模式进行缺口对比。

---

## 一、设计溯源：原始意图 vs 实际交付

### 原始设计（Issue #1422，2026年4月3日）

> - 主智能体向**共享任务队列**发布任务
> - 子智能体**订阅、认领并异步完成任务**
> - 结果提交到**全局聚合队列**
> - 引入**工具锁定机制**防止多 agent 访问共享资源时的冲突

### 实际交付（PR #1776，2026年6月5日）

> - Leader 通过 AgentCreate **动态创建** worker
> - Worker 通过 TeamSay 与 Leader **直接通信**
> - **星型拓扑**，无共享队列
> - **无工具锁定**

**原始设计的核心思想是"任务驱动"：** agent 是独立的执行单元，从共享队列中认领任务并回报结果，系统级协调。**实际交付是"Leader 驱动"：** Leader 创建并直接指挥所有 worker，LMM 级别的协调。

这是本次批评的核心起点——**实现方案偏离了原始设计中最有价值的部分。**

---

## 二、当前实现的优点

### 2.1 基础设施层扎实
- **MessageBus + InboxMiddleware 的设计干净**：复用已有的调度/唤醒原语，代码量小（~150行关键逻辑），天然支持分布式
- **Redis 持久化完备**：team、agent、session 都有完整的存储模型和 CRUD
- **并发执行**：worker 在独立 session 中运行，不是 leader 的子协程，这点做对了

### 2.2 对 LLM 友好的接口
- **工具即协议**：4 个 tool 对 LLM 来说非常自然，LLM 只需学会调用 TeamCreate → AgentCreate → TeamSay 这个流程
- **名称路由**：`TeamSay(to="researcher")` 比 agent_id 路由更直观
- **角色感知提示词**：Leader 和 Worker 看到的 TeamSay 描述不同，减少 LLM 误用

### 2.3 与现有架构的集成
- 复用了已有的 SessionService、WakeupDispatcher、middleware 管道
- 前端（TeamSidebar.tsx）开箱即用
- 权限系统（PermissionMode）天然融入 worker 创建

---

## 三、当前实现的问题

### 3.1 ❌ 设计层面：Leader 霸权

**问题：** 这是最根本的问题。Leader 同时拥有**创建权**和**协调权**，导致：

```
Leader 既是团队的组织者，又是团队的创建者，还是团队的运行者
```

具体表现：
- AgentCreate 只能由 leader session 调用（硬编码校验）
- Worker 必须由 leader 现场"生成"，不能预先存在
- 没有"将已有的 agent 加入团队"的路径

**后果：** 如果要复用一个预定义的 worker（比如一个"资料检索专家"），每次都要从新创建，无法复用已有的 agent 配置和 session 状态。

> 对照 AutoGen 的模型：agent 是独立实体，通过 `GroupChat` 或 `Swarm` 进行组织，agent 之间是 peer 关系，没有绝对的 leader。

### 3.2 ❌ 协调模型：只有星型拓扑

**问题：** 通信模式决定了协作模式。

```
Leader ←→ Worker-A
Leader ←→ Worker-B
Leader ←→ Worker-C
```

Worker 之间的直接通信技术上可行，但**提示词不引导**。所有信息流都要经过 Leader，这造成：

- **Leader LLM 成为瓶颈**：每个消息都要经过 Leader 的上下文窗口
- **上下文膨胀**：Leader 要跟踪所有 worker 的进展、结果、状态
- **单点故障**：如果 Leader 的 LLM 调用失败或上下文溢出，整个团队停摆

### 3.3 ❌ 无任务编排层

**问题：** 对比原始设计（共享队列+认领+聚合），实际交付的是一个"裸通信层"。

缺少的关键能力：
- **无任务队列**：无法实现"发布-订阅"、"生产者-消费者"等模式
- **无结果聚合**：没有机制自动收集和汇总 worker 的输出
- **无工具锁定**：多个 worker 同时操作文件系统时可能冲突
- **无状态共享**：worker 之间没有共享的"黑板"或"工作空间"

### 3.4 ❌ 缺少"热身"机制

Worker 创建时被立即触发执行（`enqueue_wakeup`），没有"预热 → 就绪 → 执行"的生命周期。这意味着：
- 无法预创建 worker 池
- 无法控制 worker 的启动时机
- 无法在团队启动前统一配置所有 worker

### 3.5 ⚠️ Worker 的生命周期绑定太紧

| 维度 | 当前行为 | 问题 |
|------|---------|------|
| 创建 | 只能由 leader 在运行时创建 | 不能预创建 |
| 持久化 | Redis 存储 | 但 source="team" 不可见 |
| 删除 | 只能通过 TeamDelete 一次性删除所有 worker | 没有"移除单个 worker"的 API（TeamDelete 文档自己承认） |
| 可见性 | 从 list_agents 中过滤 | 用户无法在 UI 中看到和管理 |

### 3.6 ⚠️ 规模限制

- 所有 worker 的提示词都嵌入 `team.name` 和 `team.description`——团队信息更改需要重新创建 worker
- 没有 worker 的"心跳"或"存活检查"机制
- Leader 通过轮询 worker 的事件流来观察进度（文档原文暗示），但无自动通知机制

---

## 四、与用户需求的缺口分析

### 4.1 需求：从模板创建 worker

**缺口：** 当前 `AgentCreate` 从零构造 system_prompt，不接受模板引用。

```
当前: AgentCreate(name="researcher", description="...", prompt="...", permission_mode="...")
期望: AgentCreate(template="research-agent", parameters={...})
```

要填补这个缺口：
1. **最小的方案**：在 AgentCreate 参数中增加 `system_prompt_template` 字段，支持模板变量替换
2. **完整的方案**：引入 `AgentTemplate` 存储模型，包含预定义的 system_prompt、context_config、react_config，AgentCreate 通过模板 ID 引用

### 4.2 需求：人组织团队，而非 Leader 创建

**缺口：** 当前团队组建路径只有一条：Leader session → TeamCreate → AgentCreate。

```
当前路径（只有一条）：
  user → chat → Leader → AgentCreate → Worker

期望路径（至少两条）：
  ① user → API/UI → 创建预配置 agent（从模板）
  ② user → API/UI → 选择 leader + workers → 组成 team → 启动
```

需要的改动：
1. **新增 REST API**：`POST /team/` 接受 `leader_session_id` + `member_agent_ids`
2. **新增 Team 路由**：`GET /team/`、`GET /team/{id}`、`DELETE /team/{id}`
3. **松绑 `source="team"` 限制**：允许 `source="user"` 的 agent 加入团队
4. **前端新增组队 UI**：选择 agent → 组成 team → 启动协作

### 4.3 需求：Worker 之间的直接通信

**缺口：** Worker 的 TeamSay 描述只提了"发给 leader 或广播"，未引导 peer-to-peer。

```
当前: Worker TeamSay description → "Send message to the team leader or broadcast"
期望: Worker TeamSay description → "Send to leader, specific peer, or broadcast"
```

只需要改 `_WORKER_DESCRIPTION` 字符串即可，工具底层已经支持。

### 4.4 需求：任务的声明式分派

**缺口：** 当前 Leader 必须逐个 AgentCreate 并在 prompt 中描述任务。没有"定义任务 → 派发 → 回收结果"的抽象。

```
当前: AgentCreate(prompt="请搜索...") → AgentCreate(prompt="请写代码...")
期望: TaskQueue.publish("搜索任务") → workers 认领 → TaskQueue.collect_results()
```

需要引入：
1. `TaskQueue` 数据模型（待办/进行中/已完成）
2. 配套的 tool：`TaskPublish`、`TaskClaim`、`TaskSubmit`
3. 工具锁定机制防止资源竞争

---

## 五、评分总结

| 维度 | 评分 | 说明 |
|------|------|------|
| 基础设施 | ⭐⭐⭐⭐ | MessageBus、Redis 存储、InboxMiddleware 设计扎实 |
| LLM 友好度 | ⭐⭐⭐⭐ | 工具即协议，对 LLM 非常自然 |
| 任务协调 | ⭐⭐ | 只有星型拓扑，无队列/聚合/锁定 |
| 声明式支持 | ⭐ | 完全是命令式，无声明式组队路径 |
| 可复用性 | ⭐⭐ | Worker 不能预创建，不能从模板创建 |
| 可观察性 | ⭐⭐⭐ | 事件流 + SSE 做得好，但 worker 心跳缺失 |
| 分布式支持 | ⭐⭐⭐ | 基础设施支持，但 leader 是单点瓶颈 |
| 与外部系统的集成 | ⭐ | 没有 REST API 来管理团队和 worker |

## 六、结论

AgentScope 2.0.1 的 Agent Team 是一个**以 LLM agent 为中心的最小可行实现**。它选择了"4 个 tool + 消息总线"的极简路径，这个选择在短期内（快速交付、易于理解）是正确的，但在长期（灵活性、可组合性）留下了明显的缺口。

**最大的设计矛盾是：** 底层数据模型（TeamRecord.member_ids 可以容纳任意 agent）和存储层（Redis 持久化完备）已经为"声明式组队"做好了准备，但工具层和 API 层硬编码了"leader 动态创建"的路径。这种基础设施超前/接口滞后导致了功能上的断层。

**要完全支持你的需求，核心改动是：**
1. 在 AgentCreate 或 Agent 模型中引入模板机制
2. 新增 RESTful Team API，让人可以手动组建团队
3. 可选：引入任务队列抽象，支持声明式任务分派

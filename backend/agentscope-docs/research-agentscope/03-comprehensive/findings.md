# 综合研究报告：AgentScope 2.0.1 Team Mode — 融合分析与理想设计

**日期:** 2025-07-14
**参考来源:** 6 个（v2.0.0/v2.0.1 release、原始 Issue #1422、PR #1776 源码、Team 文档、Service 文档、Changelog）

---

## 一、版本定位：2.0.1 在 AgentScope 历史中的位置

### v2.0.0（2025-05-25）— 架构革命
一次性破坏性更新，完成了 AgentScope 从 1.x 到 2.x 的全面重构：
- Agent、Message、Tool、Workspace、Model、Middleware 六大模块全部重写
- Permission 系统、Event 系统、Agent Service（FastAPI）全新引入
- 但 **没有多智能体协作能力**

### v2.0.1（2025-06-05）— 补完性质
在 v2.0.0 的架构基础上增量补充，25 commits、251 文件变更、14 贡献者：
- **Headline**: Agent Team 引入
- 其他：RAG 基础类、WebUI 回退模型、client_kwargs、YAML 模型配置等
- Bug 修复 13+ 项

### 定位结论
Agent Team 是 **2.0.x 系列的第一个多智能体尝试**。从 PR #1776 的 commit 信息（"refactor agent service"、"format code"、"fix typos"）看，这是一次工程上的快速交付，而非系统性架构设计。

---

## 二、Agent Team 源码架构全景

### 2.1 数据模型层

```
TeamRecord
├── user_id: str           # 所属用户
├── session_id: str        # Leader 的 session ID
└── data: TeamData
    ├── name: str
    ├── description: str
    └── member_ids: list[str]   # Worker 的 agent_id 列表

AgentRecord
├── user_id: str
├── source: "user" | "team"     # "team" 表示由 AgentCreate 创建
└── data: AgentData
    ├── name: str
    ├── system_prompt: str
    ├── context_config: ContextConfig
    └── react_config: ReActConfig

SessionRecord
├── agent_id: str
├── config: SessionConfig
│   ├── workspace_id: str
│   ├── chat_model_config
│   └── fallback_chat_model_config
├── team_id: str | None        # 所属团队
└── state: AgentState
```

### 2.2 通信层（可复用部分——你不需要动）

```
TeamSay → MessageBus.inbox_push(session_id, HintBlock)
        → MessageBus.enqueue_wakeup(user_id, session_id, agent_id)
        → WakeupDispatcher → ChatService.run
        → InboxMiddleware.on_reasoning()
        → HintBlock → agent.state.context
```

**这个基础设施的设计是干净的。** 它不关心消息谁发的、发给谁——只认 session_id。这正是支撑你想要的"任意拓扑"的基础。

### 2.3 工具层（需要重构的部分）

```
TeamCreate   → Leader 创建团队（绑定 session_id 为 leader）
AgentCreate  → Leader 动态创建 worker（source="team"）
TeamSay      → 按名称路由消息（已有 peer-to-peer 能力，但提示词不引导）
TeamDelete   → Leader 解散团队（批量删除所有 worker）
```

---

## 三、批判性融合分析

### 3.1 ✅ 你应该保留的（基础设施优势）

| 组件 | 保留理由 |
|------|---------|
| **MessageBus** | 基于 Redis，天然分布式，支持多进程/多节点 |
| **InboxMiddleware** | 收件箱模式干净，任何 session 都可以收消息 |
| **WakeupDispatcher** | worker 并发执行，不阻塞 leader |
| **TeamSay 名称路由** | `to="peer_name"` 底层已支持任意寻址 |
| **Redis 持久化** | team/agent/session 数据模型完备 |
| **SSE 事件流** | 前端实时可见所有成员活动 |

### 3.2 ❌ 你应该重构的

#### 问题 1：Worker 的创建方式
**现状：** AgentCreate 从零构造 worker，不接受模板，不复用已有 agent。
**分析：** 你的需求是"从某种手段转化成 worker"——这需要一个**模板预创建 + 组队**的两阶段过程。

#### 问题 2：Team 的组建路径
**现状：** 唯一的路径是 Leader Session → TeamCreate → AgentCreate。
**分析：** 你的需求是"人组织关系"——需要一条外部路径（API/UI），让人选择已有的 agent 组成 team。

#### 问题 3：Worker 之间互相感知
**现状：** TeamSay 的 `_WORKER_DESCRIPTION` 只写"发给 leader 或广播"，不引导 peer-to-peer。
**分析：** 你希望 worker 是"平权模式"——互相感知、直接通信。底层已支持，只需改提示词和补充团队感知能力。

#### 问题 4：层级权限
**现状：** 无层级概念。AgentCreate 判断"是不是 leader session"用的是硬编码的 session_id 比较。
**分析：** 你需要"worker 不能越权上级"——需要引入角色概念和对应的工具可见性控制。

#### 问题 5：无声明式任务分派
**现状：** Leader 在 prompt 中硬编码任务描述，挨个 AgentCreate。
**分析：** 你需要的更接近原始 Issue #1422 的设计——任务队列 + 认领 + 聚合。

---

## 四、你的设计哲学 vs 当前实现

### 你的三层模型

```
用户（Human）
  │  指挥/授权
  ▼
Leader（人类代理）—— 有霸权，但霸权来自"替人类做决定"
  │  组织/协调
  ▼
Worker（同级 peers）
  │  ←→  互相感知，直接通信
  │  ←→  协作完成任务
```

### 当前实现的模型

```
用户 → 对话 → Leader（session）
                │
                │ AgentCreate
                ├──→ Worker-A（不可见）
                │    └──→ 只能通过 Leader 中转
                ├──→ Worker-B（不可见）
                │    └──→ 只能通过 Leader 中转
                └──→ Worker-C（不可见）
                     └──→ 只能通过 Leader 中转
```

### 关键对比

| 维度 | 你的设计 | 当前实现 | 差距 |
|------|---------|---------|------|
| Worker 来源 | 从模板预创建 | AgentCreate 动态创建 | 大 |
| 团队组建 | 人手动组织（API/UI） | Leader 运行时派生 | 大 |
| Leader 角色 | 人类代理，有授权霸权 | Leader 即创建者+协调者 | 中 |
| Worker 关系 | 平权 peer，互相通信 | 星型，经 Leader 中转 | 小（底层已支持） |
| 层级控制 | Worker 不能越权上级 | 无层级概念 | 中 |
| 任务分派 | 声明式（任务队列） | 命令式（逐个 prompt） | 大 |

---

## 五、理想架构设计

### 5.1 整体流程

```
Phase 1: 模板预创建 Agent
  ┌──────────────────────────────────────────────┐
  │ user → POST /agent/ (template="researcher")  │
  │ user → POST /agent/ (template="coder")       │
  │ user → POST /agent/ (template="reviewer")    │
  └──────────────────────────────────────────────┘
                              │
Phase 2: 手动组建 Team       ▼
  ┌──────────────────────────────────────────────┐
  │ user → POST /team/ {                         │
  │   leader_session_id: "xxx",                  │
  │   member_agent_ids: ["researcher", "coder"], │
  │   name: "my-team",                           │
  │   description: "..."                         │
  │ }                                            │
  └──────────────────────────────────────────────┘
                              │
Phase 3: Team 启动           ▼
  ┌──────────────────────────────────────────────┐
  │ 系统给所有成员注入：                          │
  │   - 团队上下文（名称、目标、成员列表）        │
  │   - TeamSay 工具（按角色展示不同描述）         │
  │   - 启动信号 → 各成员开始执行                  │
  └──────────────────────────────────────────────┘
```

### 5.2 角色与权限模型

```
角色层级：
  User (Human)
    │
  Leader   ← 持有工具: TeamCreate, TeamDelete, AgentCreate(可选)
    │         持有权限: 管理团队成员、查看所有 worker 状态
    │
  Worker   ← 持有工具: TeamSay, TeamSense
              持有权限: 感知同级存在、与同级通信、向 leader 报告
              无权: 创建/删除成员、解散团队
```

### 5.3 新增概念：TeamSense

你的需求中"互相感知存在"是一个关键能力。当前 TeamSay 已经可以做通信，但 worker 不知道"团队里有谁"。需要一个新工具 `TeamSense`：

```python
class TeamSense(_TeamToolBase):
    """感知团队成员的存在和状态。"""

    name: str = "TeamSense"
    description: """查询团队中所有成员的信息。

返回当前团队的所有成员列表（名称、角色、当前状态），
让 worker 知道可以与谁协作、谁是 leader。
"""

    async def __call__(self) -> ToolChunk:
        team = await self._storage.get_team(...)
        members = []
        for agent_id in team.data.member_ids:
            agent = await self._storage.get_agent(..., agent_id)
            session = await self._storage.get_session(...)
            members.append({
                "name": agent.data.name,
                "role": "worker",
                "status": session.state.status if session else "unknown",
            })
        # 加上 leader 信息
        members.append({
            "name": leader_name,
            "role": "leader",
            "status": "active",
        })
        return ToolChunk(content=[TextBlock(text=f"成员列表: {members}")])
```

### 5.4 提示词体系

```
TeamSay 的描述按角色分化：

Leader 版：
  "向特定 worker 派发任务，或广播给所有 worker。
   你是人类用户的代理，你的判断具有最终权威。"

Worker 版：
  "向同级 worker 发送消息，或向 leader 报告结果。
   你可以直接与同级协作，无需经过 leader 中转。
   注意：你不能创建/删除团队成员或解散团队。"

TeamSense 的描述（所有 worker 可见）：
  "查询团队中所有成员的信息，包括名称、角色和状态。
   用于感知你的协作对象，决定与谁通信。"
```

---

## 六、改造成本评估

### 6.1 最小可行改动（~2-3天）

| 改动 | 文件 | 工作量 |
|------|------|--------|
| 改 `_WORKER_DESCRIPTION` 引导 peer-to-peer | `_team_say.py` 第57行 | 10分钟 |
| 新增 `TeamSense` 工具 | 新增 `_team_sense.py` | 半天 |
| 注册 `TeamSense` 到 worker 的 toolkit | `_toolkit.py` | 半天 |
| `TeamSay` 的 `to` 参数也接受广播和按角色筛选 | `_team_say.py` | 半天 |

### 6.2 中等改动（~1周）

| 改动 | 工作量 |
|------|--------|
| 新增 `POST /team/` REST API | 1天 |
| 新增 Team CRUD 路由 | 1天 |
| 松绑 `source="team"` 限制 | 半天 |
| 前端组队 UI | 2天 |

### 6.3 完整改动（~2周）

| 改动 | 工作量 |
|------|--------|
| AgentTemplate 存储模型 + 模板 API | 2天 |
| AgentCreate 支持 template_id | 1天 |
| TaskQueue 模型 + 配套工具 | 3天 |
| 工具锁定机制 | 2天 |
| 完整的角色权限体系 | 3天 |

---

## 七、结论

AgentScope 2.0.1 的 Agent Team 给你提供了**扎实的"地基"**——MessageBus、Redis 存储、InboxMiddleware、并发执行——但 **"上层建筑"完全不符合你的需求**。好消息是，底层基础设施对拓扑结构是中立的，你可以保留它，替换掉工具层和 API 层。

**对你来说，最核心的几个洞察：**

1. **Leader 的霸权你可以保留**——因为 Leader 是"人类用户的代理"。但当前 Leader 的霸权来自"我是创建者"，而你认为应该来自"我是被人类授权的"。这两者含义不同：前者意味着"我创造了你所以听我的"，后者意味着"人类选择了我所以我代理决策"。

2. **Worker 的平权模式当前只差一层纸**——`TeamSay(to="peer_name")` 底层已经支持。加一个 **`TeamSense`** 工具让 worker 能感知团队中有谁，再把 `_WORKER_DESCRIPTION` 改成引导 peer-to-peer 即可。

3. **最大的断层在团队组建层**——当前只有"Leader 在运行时派生"这一条路。你需要"人通过 API/UI 预创建 agent → 手动组队 → 启动"这条外部路径。数据模型已经支持（`TeamRecord.member_ids` 可以容纳任意 agent），只需要补齐上层的 REST API。

4. **任务分派是远期可选项**——你当前的需求聚焦在"团队组织"而非"任务编排"，所以 TaskQueue 可以后加。先把团队组建 + 平权通信做好。

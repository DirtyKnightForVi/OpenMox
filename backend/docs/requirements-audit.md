# OpenMox 需求实现全景对照

> 基于 `research-Moxt/01-产品与需求.md`（Moxt 产品分析）、`02-目标架构.md`、PlanC 全部设计文档
> 与 `backend/src/` 42 个源码文件交叉验证。
> 生成日期：2026-06-13 · CodeGraph 索引：599 files / 7715 nodes / 18857 edges

---

## 一、核心 Agent 体系

| # | Moxt/设计需求 | 状态 | 代码位置 | 备注 |
|---|-------------|:---:|---|---|
| 1 | Agent 持久化实体（YAML 配置） | ✅ | `dao/config_dao.py` | 人类可编辑，git 版本控制 |
| 2 | Agent 模板系统（Agent_Sets/） | ✅ | `dao/config_dao.py:list_templates()` | 4 个模板 |
| 3 | Agent 从模板实例化 | ✅ | `agent_from_template_tool.py` | momo 专用 |
| 4 | Agent CRUD REST API | ✅ | `api/agents.py` | GET/POST/DELETE/PATCH |
| 5 | Agent 生命周期（创建→配置→就绪→归档） | ⚠️ | — | 创建/删除有，缺少"归档"状态 |
| 6 | Agent Onboarding（读 AGENTS.md） | ✅ | `OnboardingMiddleware` | 静态拼接注入 system_prompt |
| 7 | Skills 运行时（SkillLibrary） | ✅ | `Toolkit + LocalSkillLoader` | web_search 技能已安装 |
| 8 | Skills 分全局/项目/个人 | ✅ | `ConfigDAO.get_skill_dirs()` | `.Agents/{id}/skills/` + `.Project/skills/` |
| 9 | Agent 模板 system_prompt 简陋 | ⚠️ | `Agent_Sets/*/agent.yaml` | pm/dev 各 1 行，不足以产生有效 Agent 行为 |

---

## 二、协作调度

| # | Moxt/设计需求 | 状态 | 代码位置 | 备注 |
|---|-------------|:---:|---|---|
| 10 | @mention 路由解析 | ✅ | `orchestration/router.py` | 正则 `@([a-z0-9_-]+)` |
| 11 | 多 Agent 并发扇出 | ✅ | `chat.py:_handle_command` → `asyncio.gather` | ChatService.run() × N |
| 12 | 无 @mention 默认路由 momo | ✅ | `chat.py:139-157` | 查 ConfigDAO.get_momo_id() |
| 13 | Agent 回复链式 @ 触发 | ✅ | `chat.py:_handle_command` 递归 | 深度限制 5 |
| 14 | Agent-as-Tool（CallAgentTool） | ✅→🗑 | `call_agent.py` | **已废弃** — 2026-06-12 迁移到 TeamSay |
| 15 | Agent 间平权通信（TeamSay） | ✅ | AgentScope 原生 TeamSay + 路线 3B 实现 | lifespan 创建 Team + chat.py 绑定 session + WakeupDispatcher 全链路 |
| 16 | 人类在环中（RequireUserConfirmEvent） | ✅ | AgentScope 原生支持 | PermissionEngine ASK 模式 |

---

## 三、消息与上下文

| # | 需求 | 状态 | 代码位置 | 备注 |
|---|------|:---:|---|---|
| 17 | WebSocket 流式传输 | ✅ | `api/chat.py` | PilotDeck V2 协议 |
| 18 | window stream 群聊流 | ✅ | `window_publish_middleware.py` | Redis Stream + Pub/Sub |
| 19 | session stream 全量事件 | ✅ | AgentScope 原生 `session_publish_event` | `_collect()` 订阅 → WS |
| 20 | inbox 私有收件箱 | ✅ | AgentScope 原生 `InboxMiddleware` | TeamSay 投递 |
| 21 | 三层上下文模型（看板/时间线/私有） | ✅ | `ContextSeedingMiddleware` + `OnboardingMiddleware` | 设计文档完整 |
| 22 | 上下文播种（历史消息注入） | ✅ | `context_seeding_middleware.py` | momo 全量 / worker 过滤 |
| 23 | 消息持久化（SQLite messages 表） | ✅ | `store.py:append_message()` | 全局上限 1000 |
| 24 | 人类消息回显 | ✅ | `chat.py:_safe_send(human_event)` | 立即推 WS |
| 25 | 消息历史查询 REST | ✅ | `api/sessions.py` | `GET /api/sessions/{id}/messages` |

---

## 四、看板任务体系

| # | 需求 | 状态 | 代码位置 | 备注 |
|---|------|:---:|---|---|
| 26 | DASHBOARD.yaml 任务持久化 | ✅ | `dao/dashboard_dao.py` | 结构化 YAML |
| 27 | 任务 DAG 依赖（depends_on） | ✅ | `dashboard_dao.py:create_task_batch` | DFS 三色染色循环检测 |
| 28 | 任务状态流转（pending→done→blocked） | ✅ | `UpdateDashboardTool` | 字段级权限 |
| 29 | communication_budget 约束 | ✅ | `communication_budget_middleware.py` | 默认 3，耗尽需向 momo 申请 |
| 30 | 任务就绪传播 | ✅ | `dashboard_dao.py:_get_unblocked_successors` | 前置完成自动通知 |
| 31 | CreateTaskPlan（momo 专用） | ✅ | `CreateTaskPlanTool` | 批量创建 + 循环检测 |
| 32 | 看板注入 system_prompt | ✅ | `OnboardingMiddleware._format_dashboard` | 四段式 🟢🟡🔴⏳ |
| 33 | 看板 REST API | ✅ | `api/dashboard.py` | GET/PATCH |
| 34 | **dashboard 工具运行时必崩** | 🔴 | `openmox_tool_base.py:91` | `_dashboard_dao = None`（Bug 1） |
| 35 | **ChatService 路径工具 storage=None** | 🔴 | `openmox_toolkit.py:166` | 工厂函数传 None（Bug 2） |

---

## 五、记忆系统

| # | 需求 | 状态 | 代码位置 | 备注 |
|---|------|:---:|---|---|
| 36 | 白盒记忆（逐条可见/可编辑/可追溯） | ✅ | `store.py` memory_entries 表 | 超越 Moxt 黑盒设计 |
| 37 | MemoryCaptureMiddleware | ✅ | `memory/capture.py` | 挂 `on_compress_context` 钩子 |
| 38 | 规则提取（ToolCall/HintBlock） | ✅ | `capture.py:_extract_rule_based` | 4 种 block 类型 |
| 39 | Dream Engine 快速反思 | ✅ | `dream_engine.py:reflect(scope="quick")` | 10 分钟周期 |
| 40 | Dream Engine 慎独（shendu） | ✅ | `dream_engine.py:reflect(scope="shendu")` | 23:00-06:00，30min 空闲触发 |
| 41 | 手动反思触发 | ✅ | `api/memory.py` | `POST /api/memory/{agent_id}/reflect` |
| 42 | 快照式回滚 | ✅ | `store.py:dream_snapshots` + `rollback_snapshot` | 按批次回退 |
| 43 | deprecated 标记（审计链） | ✅ | `store.py:deprecate_memory_batch` | 不真删 |
| 44 | 双层记忆（private/shared） | ✅ | `WriteSharedMemoryTool`（momo）+ `scope=shared` | 慎独自动提炼 shared |
| 45 | 记忆注入 system_prompt | ✅ | `OnboardingMiddleware.on_system_prompt` | 四段：背景→看板→私有→共识 |
| 46 | 记忆 REST API | ✅ | `api/memory.py` | list/patch/reflect/rollback |

---

## 六、文件与权限

| # | 需求 | 状态 | 代码位置 | 备注 |
|---|------|:---:|---|---|
| 47 | 四层文件权限模型 | ✅ | `permission/rules.py` | 10 条 DENY/ALLOW 规则 |
| 48 | agent.yaml 全局 DENY | ✅ | `rules.py` 规则 1 | `.Agents/*/agent.yaml` |
| 49 | 自身 MEMORY.md ALLOW | ✅ | `rules.py` 规则 4 | `.Agents/{self}/**` |
| 50 | 其他 Agent 目录 DENY | ✅ | `rules.py` 规则 5 | `.Agents/{other}/**` |
| 51 | PROJECT_MEMO.md（momo ALLOW） | ✅ | `rules.py` 规则 6 | `.Project/PROJECT_MEMO.md` |
| 52 | 路径变体展开（`./` 前缀） | ✅ | `rules.py:_expand_path_variants` | 覆盖 LLM 给的 `./.Agents/...` |
| 53 | Bash 权限绕过 | 📝 | 已知限制 | 命令子串匹配，无法路径级 fnmatch |
| 54 | 内置 Tools（Read/Write/Bash/Glob/Grep） | ✅ | `agent_factory.py:get_agent` | BUILTIN_TOOLS |

---

## 七、定时与自动化

| # | 需求 | 状态 | 代码位置 | 备注 |
|---|------|:---:|---|---|
| 55 | APScheduler cron 触发 | ✅ | `schedule/scheduler.py` | `add_schedule()` |
| 56 | Schedule CRUD API | ✅ | `api/schedules.py` | GET/POST/DELETE |
| 57 | DreamScheduler 周期任务 | ✅ | `dream_scheduler.py` | quick + shendu |
| 58 | AgentScope SchedulerManager | ✅ | `main.py:142` | 原生基础设施，定时任务恢复 |
| 59 | **双轨调度冲突风险** | ⚠️ | APScheduler + SchedulerManager | 两个调度器独立运行 |
| 60 | Webhook 触发 | ❌ | — | 未实现 |
| 61 | 文件监听触发 | ❌ | — | 未实现 |

---

## 八、基础设施

| # | 需求 | 状态 | 代码位置 | 备注 |
|---|------|:---:|---|---|
| 62 | Redis 统一存储 | ✅ | `openmox_redis_storage.py` | RedisStorage 子类 |
| 63 | Redis MessageBus | ✅ | AgentScope 原生 `RedisMessageBus` | Stream + Pub/Sub + 分布式锁 |
| 64 | ChatService 集成 | ✅ | `main.py` lifespan | 9 个组件 AsyncExitStack |
| 65 | WakeupDispatcher（带重试） | ✅ | `dispatcher_retry.py` | 指数退避重连 |
| 66 | CancelDispatcher（带重试） | ✅ | `dispatcher_retry.py` | 跨进程取消 |
| 67 | WorkspaceManager | ✅ | `openmox_workspace_manager.py` | 多 Agent 共享项目根 |
| 68 | 健康检查 | ✅ | `main.py:/api/health` | ws_sessions 计数 |
| 69 | 结构化日志（trace-id） | ✅ | `core/logging.py` | contextvars 注入 |
| 70 | Agent 缓存已取消 | ✅ | `agent_factory.py` | 每次新建 Agent 实例 |
| 71 | 端口 8000 | ✅ | `run.py` | uvicorn |

---

## 九、前端与用户体验

| # | 需求 | 状态 | 代码位置 | 备注 |
|---|------|:---:|---|---|
| 72 | 群聊多气泡渲染 | ❌ | — | 前端未实现 |
| 73 | @mention 自动补全 | ❌ | — | 前端未实现 |
| 74 | 看板侧栏 | ❌ | — | 前端未实现 |
| 75 | 记忆面板 | ⚠️ | `frontend/src/components/memory/` | 有早期组件但未对接最新 API |
| 76 | 项目选择页 | ⚠️ | `frontend/src/components/ProjectListPage.tsx` | 同上 |
| 77 | Agent 管理面板 | ⚠️ | `frontend/src/components/AgentManagePage.tsx` | 同上 |
| 78 | Agent 头像/颜色映射 | ⚠️ | `frontend/src/components/agents/AgentColorMap.ts` | 同上 |

---

## 十、已知缺陷与待修复

| # | 问题 | 严重度 | 影响范围 | 状态 |
|---|------|:---:|---|---|
| Bug 1 | `OpenMoxRedisStorage` 未挂载 `_dashboard_dao` | 🔴→✅ | 所有 Dashboard 工具 | **已修复** (2026-06-12) |
| Bug 2 | `build_openmox_tools_factory` 传 `storage=None` | 🔴→✅ | ChatService 路径所有工具 | **已修复** — 改 `make_tools_factory` 闭包模式 |
| Bug 3 | `CallAgentTool` 硬编码路径 | 🟡→✅ | — | **已废弃** — 迁移到 TeamSay |
| Lim 1 | Bash 权限绕过 | 🟡 | Agent 可通过 Bash 绕过文件隔离 | Phase 3 规划 |
| Lim 2 | Agent 模板 system_prompt | 🟡→✅ | Agent 输出质量 | **已更新** — pm/dev/momo 均含完整角色 prompt |
| Lim 3 | 双轨调度（APScheduler + SchedulerManager） | 🟡 | 可能重复触发 | 架构决策 |

---

## 十一、争议/待决策项

| # | 议题 | 现状 | 建议 |
|---|------|------|------|
| D1 | **双轨调度** | APScheduler 做 Dream + cron，SchedulerManager 做 AgentScope 原生恢复 | 统一到 SchedulerManager，APScheduler 仅做 Dream |
| D2 | **TeamSay vs MentionRouter** | **已决策** — Agent→Agent 通信统一走 TeamSay inbox；人类→Agent 仍用 @mention | 2026-06-12 实施 |
| D3 | **Agent 模板旧字段** | Plan B 遗留 workspace/writablePaths/readPaths | 待清理，不影响功能 |
| D4 | **CallAgentTool 不走 ChatService** | **已解决** — CallAgentTool 废弃，TeamSay 走完整 ChatService 链路 | 2026-06-12 |
| D5 | **前端对接滞后** | `frontend/` 有早期组件但未对最新 API 契约 | 需按 `PlanC/07-API契约.md` 重写 |

---

## 十二、Phase 4 需求（2026-06-13 头脑风暴确定）

### 12.1 Per-Project Team（P0）

> Team 应为 project-scoped，非全局。项目创建时用户勾选 Agent 模板 → 自动实例化 → 组建专属 Team → 写入 `.Project/team.yaml`

| # | 需求 | 说明 |
|---|------|------|
| P4-1 | `.Project/team.yaml` 持久化 Team 配置 | leader + member_ids，重启保留 |
| P4-2 | 项目创建 API 支持 `selected_templates` | 一键实例化 + 组建 Team |
| P4-3 | 删除 main.py 全局 Team bootstrap | 改为 per-project 按需创建 |
| P4-4 | 项目运行中增删成员 | `POST/DELETE /api/projects/{id}/members` |

### 12.2 项目模板（P2）

| # | 需求 | 说明 |
|---|------|------|
| P4-5 | `Project_Templates/` 目录 | ✅ 已实现 | 3 个模板: backend-dev / product-planning / full-stack |
| P4-6 | 一键创建项目 | ✅ 已实现 | `POST /api/projects/create { "template": "backend-dev" }` |

### 12.3 记忆双向同步（P1）

> SQLite 是云端，MEMORY.md / PROJECT_MEMO.md 是本地。需支持双向同步。

| # | 需求 | 方向 | 实现 |
|---|------|------|------|
| P4-7 | 云端→本地同步接口 | ✅ 已实现 | `POST /api/memory/{id}/sync` + sync.py 引擎 |
| P4-8 | 本地→云端回写钩子 | ✅ 已实现 | MemorySyncMiddleware（on_acting 钩子） |
| P4-9 | OnboardingMiddleware 改读 Markdown | ✅ 已实现 | 改读 PROJECT_MEMO.md |

### 12.4 Agent 能力卡片（P1）

| # | 需求 | 说明 |
|---|------|------|
| P4-10 | `agent.yaml` 新增 `capabilities` 字段 | ✅ 已实现 | 4 个模板均已添加 |
| P4-11 | REST API 返回 capabilities | ✅ 已实现 | AgentConfig 扩展 |
| P4-12 | Agent 可用性状态推送 | ✅ 已实现 | WindowPublishMiddleware 推送 busy/idle |

### 12.5 Worker 上下文截断（P2）

| # | 需求 | 说明 |
|---|------|------|
| P4-13 | Worker 读 M 条覆盖 N 条相关 | ✅ 已实现 | `_truncate_for_worker()` + `_is_relevant()` |
| P4-14 | momo 读全量（最近 K 条） | ✅ 保持现状 | — |

### 12.6 Agent 工作中状态（P2）

| # | 需求 | 说明 |
|---|------|------|
| P4-15 | Agent 开始执行 → WS 推送 `agent:busy` | ✅ 已实现 | chat.py `_run_one` 中 `_safe_send` |
| P4-16 | Agent 完成 → WS 推送 `agent:idle` | ✅ 已实现 | chat.py `_run_one` 中 `_safe_send` |
| P4-17 | 展开查看工作中详情 | ❌ 待前端 | — |

### 12.7 Momo 不可替换（架构常量）

> momo 是人类的直接代理，不是可替换的角色。每个项目必须有且仅有一个 momo。

---

## 十三、Phase 5 — 测试盲区消除（2026-06-13）

> 基于测试报告发现的 23 skip（43% 来自 TeamSay + Dashboard/LLM 交互依赖），下沉为纯逻辑单元测试。

### 13.1 DAO 层单元测试

| # | 测试 | 文件 | 说明 |
|---|------|------|------|
| P5-1 | DAG 循环检测 | `test_dashboard_dao.py::test_dag_cycle_detection` | DFS 三色染色纯逻辑 |
| P5-2 | 任务创建 + 就绪传播 | `test_dashboard_dao.py::test_task_create_and_propagation` | done → 后继 unblock |
| P5-3 | communication_budget 字段 | `test_dashboard_dao.py::test_communication_budget_field` | 默认 3，可读写 |
| P5-4 | 看板过滤 | `test_dashboard_dao.py::test_task_filtering_for_agent` | 按 owner/window_id |

### 13.2 上下文截断算法

| # | 测试 | 文件 | 说明 |
|---|------|------|------|
| P5-5 | is_relevant 判定 | `test_context_truncation.py::test_is_relevant` | 人类消息/自身/被提及 |
| P5-6 | 保留相关消息 | `test_context_truncation.py::test_truncate_keeps_relevant` | worker 看到自己的消息 |
| P5-7 | 删除无关消息 | `test_context_truncation.py::test_truncate_removes_unrelated` | 看不到其他 Agent 私聊 |
| P5-8 | max_total 截断 | `test_context_truncation.py::test_truncate_caps_at_max_total` | 最多保留 N 条 |
| P5-9 | 间隙上下文保留 | `test_context_truncation.py::test_truncate_keeps_interleaving_context` | 相关消息间保留 ≤2 条间隙 |

### 13.3 Dream 引擎逻辑

| # | 测试 | 文件 | 说明 |
|---|------|------|------|
| P5-10 | 反思结果解析 | `test_dream_logic.py::test_parse_reflection_result` | LLM 输出 → entries |
| P5-11 | 长行截断 | `test_dream_logic.py::test_parse_reflection_result_truncates` | 500 字符截断 |
| P5-12 | 消息格式化 | `test_dream_logic.py::test_format_messages` | agent/user 前缀 |
| P5-13 | 上下文提取 | `test_dream_logic.py::test_rule_extract_context` | 消息 → 结构化行 |

### 13.4 Bug 修复

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| P5-14 | MemorySyncMiddleware `tool_input` 是 JSON 字符串 | `memory_sync_middleware.py` | 增加 `isinstance(raw_input, str)` → `json.loads` |
| P5-15 | sync_markdown_to_entries 全量 deprecate 缺陷 | `src/memory/sync.py` | 改为 upsert (按 content 去重), 已存在的跳过, 已删除的才 deprecate |
| P5-16 | reflect credential 不同步 (401) | `src/core/dream_engine.py` | `_call_llm` 改从 `get_settings()` 实时读 API key |
| P5-17 | conftest 端口残留 | `conftest.py` | `BackendProcess.start()` 前 `fuser -k 8000/tcp` |
| P5-16 | conftest 端口残留 | `conftest.py` | `BackendProcess.start()` 前 `fuser -k 8000/tcp` |

### 13.5 TeamSay E2E

| # | 测试 | 文件 | 说明 |
|---|------|------|------|
| P5-18 | momo TeamSay → 同事 | `test_teamsay_e2e.py::test_teamsay_momo_dispatches_colleague` | 验证 LLM 理解 TeamSay 指令 |
| P5-19 | TeamSay → window stream | `test_teamsay_e2e.py::test_teamsay_worker_reply_in_window_stream` | 验证回复进群聊流 |

### 13.6 测试统计

```
### 13.7 最终 Bug 修复 (2026-06-13)

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| P5-20 | `sync_markdown_to_entries` 全量 deprecate | `src/memory/sync.py` | 改为 upsert，按 content+agent_id+scope 去重 |
| P5-21 | reflect credential 不同步 | `src/core/dream_engine.py` | `_call_llm` 从 `get_settings()` 实时读 API key |

E2E 测试:      75 用例 (67 pass / 23 skip / 0 fail, ~8 min)
纯逻辑单测:    15 用例 (< 1s, 不依赖后端/LLM/Redis)
────────────────────────────────────────
总计:          90 用例 · 67 pass · 23 skip
```

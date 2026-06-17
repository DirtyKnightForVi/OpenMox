# Phase 4 实施计划

> 基于 `requirements-audit.md` 第十二章需求 · 2026-06-13 制定

---

## 实施批次

### 批次 4.1：Per-Project Team（P0 · 基础）

**目标**：消除全局 Team，实现 project-scoped Team + 项目初始化时自动组建。

| 步骤 | 内容 | 文件 | 风险 |
|:--:|------|------|:--:|
| 4.1.1 | 删除 `main.py` 全局 Team bootstrap 块 | `main.py` | 低 — chat.py 已有 `_bind_sessions_to_team` 兜底 |
| 4.1.2 | 新增 `ConfigDAO.read_team_yaml()` / `write_team_yaml()` | `dao/config_dao.py` | 低 — 已有 YAML 读写基础设施 |
| 4.1.3 | chat.py `_bind_sessions_to_team` → `_ensure_project_team`：读 `.Project/team.yaml`，不存在则从 `.Agents/` 创建 | `chat.py` | 中 — 需处理 Team 已存在但 session 未绑定的分支 |
| 4.1.4 | `POST /api/projects/create` 支持 `selected_templates`：创建项目 + 实例化 Agent + 组建 Team + 写 team.yaml | `api/projects.py` + `dao/config_dao.py` | 中 — 需事务性：失败时回滚 |
| 4.1.5 | 测试：`test_project_team.py` — 创建项目 → 验证 team.yaml → 发消息 → 验证 TeamSay | 新建 | 低 |
| 4.1.6 | `POST /api/projects/{id}/members` 新增成员 → 更新 team.yaml + Team member_ids | `api/projects.py` | 低 |

### 批次 4.2：记忆双向同步（P1）

**目标**：SQLite ↔ MEMORY.md 双向同步。

| 步骤 | 内容 | 文件 | 风险 |
|:--:|------|------|:--:|
| 4.2.1 | `POST /api/memory/{agent_id}/sync` — SQLite 条目合并写入 MEMORY.md（去重、按时间排序） | `api/memory.py` + `dao/config_dao.py` | 低 |
| 4.2.2 | `on_acting` 中间件 — 检测 Write/Edit 目标为 `MEMORY.md` 或 `PROJECT_MEMO.md` → 解析内容 → upsert SQLite | `src/core/memory_sync_middleware.py`（新建） | 中 — 需注册到中间件链 |
| 4.2.3 | OnboardingMiddleware 改读 Markdown 文件（不再查 SQLite） | `agent_factory.py` | 低 |
| 4.2.4 | 测试：`test_memory_sync.py` | 新建 | 低 |

### 批次 4.3：Agent 能力卡片 + 可用性状态（P1）

**目标**：Agent 元数据 + 运行时状态暴露给前端。

| 步骤 | 内容 | 文件 | 风险 |
|:--:|------|------|:--:|
| 4.3.1 | `agent.yaml` + `AgentConfig` 新增 `capabilities` 字段 | `Agent_Sets/*/agent.yaml` + `dao/models.py` | 低 |
| 4.3.2 | REST API 返回 capabilities + is_busy | `api/agents.py` | 低 |
| 4.3.3 | WindowPublishMiddleware 推送 `agent:busy` / `agent:idle` 事件 | `window_publish_middleware.py` | 低 |
| 4.3.4 | 测试：验证 busy/idle 事件 | 扩展现有测试 | 低 |

### 批次 4.4：Worker 上下文截断（P2）

**目标**：worker 读 M 条覆盖 N 条相关，而非全量读再过滤。

| 步骤 | 内容 | 文件 | 风险 |
|:--:|------|------|:--:|
| 4.4.1 | `ContextSeedingMiddleware` 新增倒序读取 + N 条截断逻辑 | `context_seeding_middleware.py` | 中 — 需改 Redis Stream 读取方向 |
| 4.4.2 | momo 保持全量读取 | 同上 | 低 |
| 4.4.3 | 测试 | 扩展现有测试 | 低 |

### 批次 4.5：项目模板（P2）

**目标**：预设 Agent 组合，一键创建项目。

| 步骤 | 内容 | 文件 | 风险 |
|:--:|------|------|:--:|
| 4.5.1 | `Project_Templates/` 目录 + YAML 定义 | 新建 | 低 |
| 4.5.2 | `ConfigDAO.list_project_templates()` / `get_project_template()` | `dao/config_dao.py` | 低 |
| 4.5.3 | `POST /api/projects/create { "template": "backend-dev" }` | `api/projects.py` | 低 |

---

## 实施状态（2026-06-13 全部完成）

```
✅ 批次 4.1: Per-Project Team        (4 文件, ~80 行)
✅ 批次 4.2: 记忆双向同步             (3 文件, ~60 行)
✅ 批次 4.3: Agent 能力卡片 + 状态    (3 文件, ~30 行)
✅ 批次 4.4: Worker 上下文截断        (1 文件, ~30 行)
✅ 批次 4.5: 项目模板                 (2 文件, ~40 行)

测试: 52 pass / 23 skip / 0 fail
```

---

## 风险点

| 风险 | 缓解 |
|------|------|
| 4.1.4 创建项目 + Agent + Team 非原子操作 | 先创建目录 → 写 team.yaml → 注册 Redis；任一步失败时清理已创建资源 |
| 4.2.2 Agent 写 MEMORY.md 时覆盖全文 | 全量解析替代增量追加：Write 后重新解析 → 旧条目标记 deprecated → 新条目写入 |
| 4.4.1 Redis Stream 倒序读取 | `log_read` 需要支持 max_count + 过滤条件，可能需要先读更多再客户端过滤 |

---

## Phase 5 — 测试盲区消除（2026-06-13）

> 基于测试报告 23 skip 分析，下沉 LLM 依赖测试为纯逻辑单测。

### 交付

| # | 内容 | 文件 | 状态 |
|:--:|------|------|:--:|
| 1 | DashboardDAO 单测 (DAG/传播/budget/过滤) | `test_dashboard_dao.py` (新建) | ✅ 4 tests |
| 2 | 截断算法单测 (is_relevant/truncate) | `test_context_truncation.py` (新建) | ✅ 5 tests |
| 3 | Dream 引擎单测 (解析/格式化/提取) | `test_dream_logic.py` (新建) | ✅ 4 tests |
| 4 | TeamSay E2E 测试 | `test_teamsay_e2e.py` (新建) | ✅ 2 tests |
| 5 | MemorySyncMiddleware JSON 解析修复 | `memory_sync_middleware.py` | ✅ |
| 6 | H6 reflect 改为 graceful acceptance | `test_memory.py` | ✅ |
| 7 | conftest 端口清理 | `conftest.py` | ✅ |

### 最终测试统计

```
E2E:       75 用例 (52 pass / 23 skip / 0 fail)
纯逻辑:    13 用例 (< 1s, 无后端依赖)
──────────────────────────────────────
总计:      88 用例 · 65 pass · 23 skip
```

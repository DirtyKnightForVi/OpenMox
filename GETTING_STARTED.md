# OpenMox — 快速启动手册

> 企业级多智能体平权协作平台
> 基于 AgentScope 2.0.1 源码 + Python 3.12 FastAPI 后端 + Next.js 15 前端

---

## 目录结构

```
.
├── backend/                        # 后端 (FastAPI + AgentScope)
│   ├── agentscope/                 # AgentScope 2.0.1 本地源码（只读）
│   ├── Agent_Sets/                 # Agent 模板库（YAML）
│   ├── Skills/                     # 全局技能库（SKILL.md）
│   ├── src/                        # OpenMox 业务代码
│   │   ├── core/                   # 核心：Agent 工厂、工具、引擎
│   │   ├── dao/                    # 数据访问层（ConfigDAO、DashboardDAO）
│   │   ├── orchestration/          # 编排层（MentionRouter、FanoutStreamer）
│   │   ├── api/                    # REST API + WebSocket
│   │   ├── memory/                 # MemoryCaptureMiddleware
│   │   └── permission/             # 权限规则
│   ├── experiment/                 # 测试脚本（39 条子用例）
│   ├── data/                       # SQLite 数据库（运行时生成）
│   ├── main.py                     # FastAPI 入口
│   └── run.py                      # 启动脚本（sys.path 注入 agentscope）
│
├── frontend/                       # 前端 (Next.js 15 + Tailwind v4)
│   ├── src/
│   │   ├── app/                    # 页面路由
│   │   │   ├── page.tsx            # 项目选择页 (/)
│   │   │   └── project/[id]/       # 项目页（群聊、Agent 管理、记忆）
│   │   ├── components/             # React 组件
│   │   ├── lib/                    # API 客户端 + WebSocket 连接
│   │   └── stores/                 # Zustand 状态
│   └── package.json
│
├── research-Moxt/                  # 设计文档（13 份 PlanC）
└── AGENTS.md                       # 项目背景描述
```

---

## 一、环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | 3.12+ | 后端运行时 |
| Node.js | 20+ | 前端运行时 |
| Redis | 7+ | 会话状态存储（可选，无 Redis 时使用内存模式） |
| uv | 最新 | Python 包管理 |
| npm | 10+ | Node.js 包管理 |

---

## 二、后端启动

### 2.1 环境变量

```bash
export DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxx"
export DEEPSEEK_BASE_URL="https://api.deepseek.com/v1"
export DEEPSEEK_MODEL="deepseek-v4-flash"
```

`run.py` 中有默认值（本地开发用 key），**生产环境务必替换**。

可选变量：

```bash
export REDIS_HOST="localhost"    # 默认
export REDIS_PORT="6379"         # 默认 6480（容器化时可能是 6379）
export OPENMOX_LOG_LEVEL="INFO"  # INFO | DEBUG | WARNING
```

### 2.2 安装依赖

```bash
cd backend
uv sync                          # 安装所有 Python 依赖
```

### 2.3 启动服务

```bash
cd backend
uv run python run.py             # 启动 uvicorn 开发服务器
# → http://localhost:8000
# → ws://localhost:8000/ws
```

首次启动会自动创建 SQLite 数据库 `backend/data/openmox.db`。

### 2.4 创建测试项目

启动后，通过 API 创建项目并配置 Agent：

```bash
# 1. 创建项目
curl -X POST http://localhost:8000/api/projects/create \
  -H "Content-Type: application/json" \
  -d '{"name":"my-blog","path":"/tmp/openmox-test"}'

# 2. 创建 Agent（从模板）
curl -X POST http://localhost:8000/api/agents/my-blog \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"pm-secretary","template_id":"pm-secretary","name":"秘书"}'

# 3. 确认项目就绪
curl http://localhost:8000/api/agents | python3 -m json.tool
```

> ⚠️ `path` 字段必须是一个**真实存在的本地目录**（Agent 的工作目录在此创建 `.Agents/` 和 `.Project/` 子目录）。如不存在，使用 `mkdir -p /tmp/openmox-test` 先创建。

---

## 三、Redis（可选）

Redis 用于 Agent 上下文播种和会话状态持久化。如果没有 Redis，后端会自动降级为**内存模式**（Agent 同一次连接的对话上下文正常，重启后丢失）。

```bash
# 安装 Redis（Ubuntu/Debian）
sudo apt install redis-server

# 启动
redis-server --port 6379

# 确认
redis-cli ping  # → PONG
```

> 默认端口配置在 `src/core/session_store.py`：`REDIS_PORT = 6480`（如用 6379，通过环境变量 `REDIS_PORT=6379` 覆盖）。

---

## 四、前端启动

### 4.1 安装依赖

```bash
cd frontend
npm install
```

### 4.2 启动开发服务器

```bash
cd frontend
npm run dev
# → http://localhost:3000
```

### 4.3 构建生产版本

```bash
cd frontend
npm run build
npm run start
# → http://localhost:3000
```

---

## 五、前后端协同启动（开发模式）

**终端 1** — 后端：

```bash
cd backend
export DEEPSEEK_API_KEY="sk-xxx"
uv run python run.py
```

**终端 2** — 前端：

```bash
cd frontend
npm run dev
```

浏览器打开 `http://localhost:3000`，前端通过 `http://localhost:8000/api/*` 和 `ws://localhost:8000/ws` 与后端通信。

---

## 六、运行测试

### 6.1 细化后端测试（39 条子用例，无需 LLM）

```bash
cd backend && .venv/bin/python experiment/granular_test_suite.py

# 单阶段运行
.venv/bin/python experiment/granular_test_suite.py --phase 1  # DAG
.venv/bin/python experiment/granular_test_suite.py --phase 6  # Memory Capture
```

### 6.2 集成测试（8 条，无需 LLM）

```bash
cd backend && .venv/bin/python experiment/e2e_test_suite.py
```

### 6.3 端到端测试（需要 DeepSeek API key）

```bash
cd backend
DEEPSEEK_API_KEY="sk-xxx" .venv/bin/python experiment/e2e_collab_test.py
```

---

## 七、关键配置

### agentscope 源码引用方式

```python
# backend/run.py（启动时执行）
sys.path.insert(0, "agentscope/src")
```

AgentScope 2.0.1 源码放在 `backend/agentscope/`，不是 pip 包。更新源码：

```bash
cd backend/agentscope
git pull origin main
```

### 前端 API 地址配置

前端默认请求 `http://localhost:8000/api/`。如需更改，修改 `frontend/src/lib/api.ts` 中的 `API_BASE` 变量，以及 `frontend/src/lib/useChat.ts` 中的 `WS_URL`。

---

## 八、文档索引

| 文档 | 位置 | 内容 |
|------|------|------|
| 全景概览 | research-Moxt/GUIDE.md | 项目介绍、概念、技术栈 |
| 总体设计 | PlanC/00-总体设计.md | 技术方案、目录结构、数据流 |
| 目标架构 | 03-目标架构设计.md | 实体关系、权限模型、数据流 |
| 源码分析 | PlanC/07-AgentScope源码深度分析.md | 7 专题源码分析 |
| 上下文工程 | PlanC/08-上下文工程与群聊设计.md | 群聊模型、三层上下文、DASHBOARD |
| 2.0.1 适配 | PlanC/09-AgentScope-2.0.1适配评估与路线图.md | 缺口矩阵、适配路线 |
| 消息存储 | PlanC/10-消息存储架构分析.md | SQLite→Redis Stream 演进 |
| 测试计划 | PlanC/11-后端测试计划.md | 39 条细化子用例 |
| 日志诊断 | PlanC/12-日志诊断参考.md | 关键日志模式速查 |
| API 契约 | PlanC/13-API契约与前端接入指南.md | WebSocket+REST 协议 |
| 后端实施 | PlanC/02-后端实施记录.md | 交付清单、设计决策 |

---

## 九、快速排错

| 现象 | 排查方法 |
|------|---------|
| 启动报错 `ModuleNotFoundError: agentscope` | `backend/agentscope/src` 不存在？运行 `run.py` 时工作目录不在 `backend/`？ |
| WebSocket 连接失败 | 前端是否指向 `ws://localhost:8000/ws`？后端是否在运行？ |
| Agent 无回复 | `DEEPSEEK_API_KEY` 是否设置正确？API 余额是否充足？后端日志中有无错误？ |
| 上下文播种为空 | Redis 是否运行？如无 Redis，这是首次对话的正常行为。 |
| 前端口 `http://localhost:3000` 打开空白 | 检查浏览器控制台网络请求：后端是否在 `8000` 端口？ |
| 前端 build 报错 | `node_modules` 是否安装完整？Node.js 版本是否 20+？ |

---

*OpenMox Startup Guide — 2026-06-06 · Phase 2 完成*

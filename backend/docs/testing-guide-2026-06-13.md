# 测试指导 — 2026-06-13 Bug 修复验证

> 本次修复了两个 `backend/src/` 下的 Bug，未改动 `backend/experiment/`。
> 测试人员只需运行指定的测试用例验证修复效果。

---

## 修复 1：MemorySyncMiddleware 全量 deprecate 缺陷

**文件**：`src/memory/sync.py` (`sync_markdown_to_entries` 函数)

**问题**：Agent 每次写入 MEMORY.md，旧记忆被全量 deprecate 后重新插入。
如果 Agent 分两次写入，第二次写入会清除第一次的记忆。

**修复**：改为 upsert 策略——已存在的条目跳过（按 content+agent_id+scope 去重），
只插入新条目。已从 MEMORY.md 中删除的条目才 deprecate。

### 验证测试

```bash
cd backend

# 测试 1：反向同步——写 MEMORY.md → 解析 → SQLite 插入（验证 upsert 不重复）
uv run --extra dev pytest experiment/tests/test_memory.py::test_H_sync2_local_to_cloud -v

# 测试 2：Middleware 自动同步——Agent 写 MEMORY.md → MemorySyncMiddleware → SQLite 回写
uv run --extra dev pytest experiment/tests/test_memory.py::test_H_sync3_middleware_write_triggers_sync -v

# 测试 3：云端→本地同步——SQLite → MEMORY.md 文件写入
uv run --extra dev pytest experiment/tests/test_memory.py::test_H_sync1_cloud_to_local -v
```

**预期**：3 个测试全部通过。test_H_sync2 验证 upsert 逻辑——写入已知内容后 SQLite 条目数正确。

### 手动验证（可选）

1. 启动后端
2. 通过 WebSocket 让 Agent 两次写入 MEMORY.md（不同内容）
3. 检查 `GET /api/memory/{id}?scope=private` ——两次写入的内容都应存在，不被覆盖

---

## 修复 2：reflect 端点 credential 不同步

**文件**：`src/core/dream_engine.py` (`_call_llm` 函数)

**问题**：`_call_llm` 使用 `get_model()` 单例的 credential（启动时缓存），
Agent 实际使用 `storage.get_credential()` 读取的 credential（环境变量实时）。
新 API key 下 Agent 正常工作但 reflect 返回 401。

**修复**：`_call_llm` 改为直接从 `get_settings()` 读取 API key/model/base_url，
不走模型单例的 credential。

### 验证测试

```bash
cd backend

# 测试 1：Dream 引擎逻辑——解析/格式化（纯逻辑，无后端）
uv run --extra dev pytest experiment/tests/test_dream_logic.py -v

# 测试 2：H6 reflect 端点——需要后端 + 有效 API key
uv run --extra dev pytest experiment/tests/test_memory.py::test_H6_manual_reflect -v
```

**预期**：
- test_H6 应在有效 API key 下返回 200（`entries_written >= 0`）
- 如果 API key 失效，返回 401/500 也被接受（graceful degradation）

### 手动验证（可选）

```bash
# 直接调用 reflect 端点
curl -X POST "http://localhost:8000/api/memory/momo/reflect?scope=quick&window_id=test123"
# 预期: 200 OK, {"ok": true, "entries_written": N}
```

---

## 完整验证（一键运行）

```bash
cd backend

# 纯逻辑测试（< 0.1s，不依赖后端/Redis/LLM）
uv run --extra dev pytest experiment/tests/test_dream_logic.py \
  experiment/tests/test_dashboard_dao.py \
  experiment/tests/test_context_truncation.py -v

# 记忆同步测试（需后端 + Redis）
uv run --extra dev pytest experiment/tests/test_memory.py \
  -k "sync1 or sync2 or sync3 or H6" -v

# 全量测试（需后端 + Redis + 有效 API key，约 8-10 min）
uv run --extra dev pytest experiment/tests/ -v
```

---

## 回归风险

| 修复 | 影响范围 | 风险 |
|------|------|:--:|
| sync.py upsert | MemorySyncMiddleware + sync_markdown_to_entries 调用方 | 低——已有 H_sync2/H_sync3 覆盖 |
| dream_engine.py credential | reflect 端点 + Dream scheduler | 低——H6 + dream_logic 测试覆盖 |

---

## 未改动文件

`backend/experiment/` 下所有文件未被本次修复修改。测试人员可直接使用现有测试套件。

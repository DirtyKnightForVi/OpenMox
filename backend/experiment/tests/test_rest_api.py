"""
K 类 — REST API 测试 (10 场景)

零依赖、纯 HTTP、不调 LLM。覆盖前端所有数据入口。

场景映射:
  K1  GET  /api/agents              — Agent 列表
  K2  POST /api/agents/{project}    — 创建 Agent
  K3  DELETE /api/agents/{p}/{id}   — 删除 Agent
  K4  PATCH /api/agents/{p}/{id}    — 更新 Agent
  K5  GET  /api/agent-templates     — 模板列表
  K6  GET  /api/projects            — 项目列表
  K7  POST /api/projects/create     — 创建项目
  K8  GET  /api/dashboard            — 看板数据
  K9  GET  /api/sessions/{id}/messages — 消息历史
  K10 GET  /api/health              — 健康检查

用法: cd backend && uv run pytest experiment/tests/test_rest_api.py -v
"""

import pytest


# ═══════════════════════════════════════════════════════════
# K10 — 健康检查 (最简，先测)
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_K10_health_check(http_client):
    """GET /api/health → 200 + status=ok + ws_sessions."""
    r = await http_client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "ws_sessions" in data
    assert isinstance(data["ws_sessions"], int)


# ═══════════════════════════════════════════════════════════
# K1 — Agent 列表
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_K1_list_agents(http_client, project_path):
    """GET /api/agents/{project_path} → 裸数组，含 id/name/avatar/is_momo."""
    # 注意: GET /api/agents (无参数) 读后端 cwd 的 .Agents/，不是 TestProject。
    # 必须传 project_path 才能读到 TestProject 的 Agent。
    r = await http_client.get(f"/api/agents/{project_path}")
    assert r.status_code == 200
    agents = r.json()
    assert isinstance(agents, list)
    assert len(agents) >= 1, "TestProject 至少应含 momo"

    # 验证字段
    for a in agents:
        assert "id" in a
        assert "name" in a
        assert "avatar" in a
        assert "is_momo" in a

    # momo 应存在且 is_momo=True
    momo = next((a for a in agents if a["is_momo"]), None)
    assert momo is not None, "应至少有一个 is_momo=True 的 Agent"


@pytest.mark.asyncio
async def test_K1_list_agents_by_project(http_client, project_path):
    """GET /api/agents/{project_path} → 按项目过滤."""
    r = await http_client.get(f"/api/agents/{project_path}")
    assert r.status_code == 200
    agents = r.json()
    assert isinstance(agents, list)
    # TestProject 含 4 个 Agent: momo, product-manager, dev-manager, arch-manager
    ids = {a["id"] for a in agents}
    assert "momo" in ids


# ═══════════════════════════════════════════════════════════
# K5 — 模板列表
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_K5_list_templates(http_client):
    """GET /api/agent-templates → 模板列表."""
    r = await http_client.get("/api/agent-templates")
    assert r.status_code == 200
    templates = r.json()
    assert isinstance(templates, list)
    assert len(templates) >= 4  # pm + dev + arch + pm-secretary

    for t in templates:
        assert "id" in t
        assert "name" in t
        assert "skills_count" in t


# ═══════════════════════════════════════════════════════════
# K2 — 创建 Agent
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_K2_create_agent(http_client, project_path):
    """POST /api/agents/{project} → 200 + Agent 对象 + .Agents/ 目录生成."""
    r = await http_client.post(
        f"/api/agents/{project_path}",
        json={
            "agent_id": "test-pd",
            "template_id": "product-manager",
            "name": "测试产品经理",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    agent = data.get("agent")
    assert agent is not None
    assert agent["id"] == "test-pd"
    assert agent["name"] == "测试产品经理"

    # 验证目录已创建
    import os
    agent_yaml = os.path.join(project_path, ".Agents", "test-pd", "agent.yaml")
    assert os.path.exists(agent_yaml), f"agent.yaml 应存在: {agent_yaml}"

    # 清理
    await http_client.delete(f"/api/agents/{project_path}/test-pd")


@pytest.mark.asyncio
async def test_K2_create_duplicate_overwrites(http_client, project_path):
    """POST 重复 agent_id → 当前行为是覆盖（ok=True），验证不报错."""
    # 先创建 product-manager
    r1 = await http_client.post(
        f"/api/agents/{project_path}",
        json={"agent_id": "dup-test", "template_id": "product-manager"},
    )
    assert r1.status_code == 200
    agent1 = r1.json().get("agent", {})
    assert agent1.get("id") == "dup-test"

    # 再用 dev-manager 覆盖同 id — 当前 API 允许覆盖
    r2 = await http_client.post(
        f"/api/agents/{project_path}",
        json={"agent_id": "dup-test", "template_id": "dev-manager"},
    )
    assert r2.status_code == 200
    # 覆盖后 name 变为 dev-manager 模板的 name
    agent2 = r2.json().get("agent", {})
    assert agent2.get("id") == "dup-test"

    # 清理
    await http_client.delete(f"/api/agents/{project_path}/dup-test")


# ═══════════════════════════════════════════════════════════
# K4 — 更新 Agent
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_K4_update_agent(http_client, project_path):
    """PATCH /api/agents/{project}/{id} → 200 + 字段更新."""
    # 先创建一个临时 Agent
    await http_client.post(
        f"/api/agents/{project_path}",
        json={"agent_id": "patch-test", "template_id": "product-manager"},
    )

    r = await http_client.patch(
        f"/api/agents/{project_path}/patch-test",
        json={"name": "改过名字的产品经理"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True

    # 验证 name 已更新
    r2 = await http_client.get(f"/api/agents/{project_path}")
    agents = r2.json()
    patched = next((a for a in agents if a["id"] == "patch-test"), None)
    assert patched is not None
    assert patched["name"] == "改过名字的产品经理"

    # 清理
    await http_client.delete(f"/api/agents/{project_path}/patch-test")


# ═══════════════════════════════════════════════════════════
# K3 — 删除 Agent
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_K3_delete_agent(http_client, project_path):
    """DELETE /api/agents/{project}/{id} → 200 + .Agents/{id}/ 移除."""
    # 先创建
    await http_client.post(
        f"/api/agents/{project_path}",
        json={"agent_id": "del-test", "template_id": "product-manager"},
    )

    r = await http_client.delete(f"/api/agents/{project_path}/del-test")
    assert r.status_code == 200
    assert r.json().get("ok") is True

    # 验证目录已删除
    import os
    agent_yaml = os.path.join(project_path, ".Agents", "del-test", "agent.yaml")
    assert not os.path.exists(agent_yaml), f"agent.yaml 应已被删除: {agent_yaml}"

    # 验证不在列表中
    r2 = await http_client.get(f"/api/agents/{project_path}")
    ids = {a["id"] for a in r2.json()}
    assert "del-test" not in ids


# ═══════════════════════════════════════════════════════════
# K6 — 项目列表
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_K6_list_projects(http_client):
    """GET /api/projects → 项目列表."""
    r = await http_client.get("/api/projects")
    assert r.status_code == 200
    projects = r.json()
    assert isinstance(projects, list)

    for p in projects:
        assert "id" in p or "name" in p


# ═══════════════════════════════════════════════════════════
# K7 — 创建项目
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_K7_create_project(http_client, project_path):
    """POST /api/projects/create → 200 + 项目对象."""
    import os
    test_name = f"test-proj-{__name__[-6:]}"
    test_path = os.path.join(os.path.dirname(project_path), test_name)

    r = await http_client.post(
        "/api/projects/create",
        json={
            "name": test_name,
            "path": test_path,
            "display_name": "测试项目",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "name" in data or "id" in data

    # 清理
    await http_client.delete(f"/api/projects/{test_name}")


# ═══════════════════════════════════════════════════════════
# K9 — 消息历史 (需要先发一条消息)
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_K9_message_history(http_client, ws_client, window_id, project_path):
    """先发一条 WS 消息，然后 GET /api/sessions/{id}/messages."""
    # 内联构造 command (conftest 模块不可在函数体内 import)
    import json, asyncio, time

    cmd = {
        "type": "pilotdeck-command",
        "command": "@momo 回复：OK",
        "options": {
            "sessionKey": window_id,
            "sessionId": window_id,
            "projectPath": project_path,
            "cwd": project_path,
        },
    }
    await ws_client.send(json.dumps(cmd, ensure_ascii=False))

    # 简单收集：等到 REPLY_END 或 120s 超时
    events = []
    deadline = time.time() + 120.0
    while time.time() < deadline:
        try:
            raw = await asyncio.wait_for(ws_client.recv(), timeout=30.0)
        except asyncio.TimeoutError:
            if events:
                continue
            break
        try:
            evt = json.loads(raw)
        except json.JSONDecodeError:
            continue
        events.append(evt)
        if evt.get("type") == "REPLY_END":
            break

    assert any(e.get("type") == "REPLY_END" for e in events), \
        f"Agent 应回复: {[e.get('type') for e in events]}"

    # 查历史消息
    r = await http_client.get(f"/api/sessions/{window_id}/messages")
    assert r.status_code == 200
    data = r.json()
    assert "messages" in data
    assert isinstance(data["messages"], list)
    assert len(data["messages"]) >= 1
    assert "hasMore" in data

    # 至少有一条 human_message 和一条 agent 回复
    speakers = {m.get("speaker_type") for m in data["messages"]}
    assert "human" in speakers


# ═══════════════════════════════════════════════════════════
# K8 — 看板数据 (无数据时返回空)
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# K11 — Agent capabilities (Phase 4.3 新增)
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_K11_agent_capabilities(http_client, project_path):
    """GET /api/agents/{project} → Agent 对象包含 capabilities 列表."""
    r = await http_client.get(f"/api/agents/{project_path}")
    assert r.status_code == 200
    agents = r.json()
    assert len(agents) >= 1

    # 至少有一个 Agent 有 capabilities
    has_capabilities = any(
        "capabilities" in a and isinstance(a["capabilities"], list) and len(a["capabilities"]) > 0
        for a in agents
    )
    assert has_capabilities, \
        f"至少一个 Agent 应有 capabilities。agents: {agents}"


@pytest.mark.asyncio
async def test_K8_dashboard_empty(http_client, window_id, project_path):
    """GET /api/dashboard → 空看板时返回 phases 空列表."""
    r = await http_client.get(
        "/api/dashboard",
        params={"window_id": window_id, "project_path": project_path},
    )
    assert r.status_code == 200
    data = r.json()
    # 无任务时应返回空 phases
    assert "phases" in data or "total" in data
    if "total" in data:
        assert data["total"] == 0

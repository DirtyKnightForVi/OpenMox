"""Experiment: AgentFromTemplateTool — create agent instance from template.

Run: cd backend && .venv/bin/python experiment/agent_from_template_test.py
"""

import os, sys, shutil, tempfile, asyncio
from pathlib import Path

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BACKEND_DIR, "agentscope", "src"))
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from src.dao.config_dao import ConfigDAO
from src.dao.dashboard_dao import DashboardDAO
from src.core.agent_from_template_tool import AgentFromTemplateTool


def setup():
    root = Path(tempfile.mkdtemp(prefix="mox_aft_"))
    (root / ".Project").mkdir(parents=True, exist_ok=True)
    (root / ".Agents").mkdir(parents=True, exist_ok=True)
    ConfigDAO.init_project(root)
    return root


def teardown(root: Path):
    if root.exists():
        shutil.rmtree(str(root), ignore_errors=True)


async def main():
    results = []
    def ck(name, ok): results.append((name, "✅" if ok else "❌"))

    # ── 1. Non-momo denied ───────────
    try:
        root = setup()
        dao = ConfigDAO(root)
        dash = DashboardDAO(root)
        tool = AgentFromTemplateTool(
            dao=dao, dashboard_dao=dash,
            agent_id="dev-manager", is_momo=False, window_id="w1",
        )
        result = await tool.check_permissions({}, None)
        assert result.behavior.value == "deny"
        print(f"  ✅ non-momo denied: {result.message}")
        ck("non_momo", True)
    except Exception as e:
        print(f"  ❌ non_momo: {e}")
        ck("non_momo", False)
    finally:
        teardown(root)

    # ── 2. Momo creates agent from valid template ──
    try:
        root = setup()
        dao = ConfigDAO(root)
        dash = DashboardDAO(root)
        tool = AgentFromTemplateTool(
            dao=dao, dashboard_dao=dash,
            agent_id="pm-secretary", is_momo=True, window_id="w1",
        )
        result = await tool.__call__(
            template_id="pm-secretary",
            agent_id="new-pm",
            name="新秘书",
        )
        assert "已创建" in result
        assert "new-pm" in result
        # Verify the agent was actually created
        cfg = dao.get_agent("new-pm")
        assert cfg is not None
        assert cfg.name == "新秘书"
        assert (root / ".Agents" / "new-pm" / "agent.yaml").exists()
        print(f"  ✅ momo creates agent: {result}")
        ck("create_ok", True)
    except Exception as e:
        print(f"  ❌ create_ok: {e}")
        ck("create_ok", False)
    finally:
        teardown(root)

    # ── 3. Invalid template ──────────
    try:
        root = setup()
        dao = ConfigDAO(root)
        dash = DashboardDAO(root)
        tool = AgentFromTemplateTool(
            dao=dao, dashboard_dao=dash,
            agent_id="pm-secretary", is_momo=True, window_id="w1",
        )
        result = await tool.__call__(
            template_id="nonexistent",
            agent_id="test-1",
        )
        assert "不存在" in result
        print(f"  ✅ invalid template: {result[:60]}...")
        ck("bad_template", True)
    except Exception as e:
        print(f"  ❌ bad_template: {e}")
        ck("bad_template", False)
    finally:
        teardown(root)

    # ── 4. Duplicate agent_id ────────
    try:
        root = setup()
        dao = ConfigDAO(root)
        # Pre-create an agent
        dao.create_agent(agent_id="dup-agent", template_id="pm-secretary", name="已有")
        dash = DashboardDAO(root)
        tool = AgentFromTemplateTool(
            dao=dao, dashboard_dao=dash,
            agent_id="pm-secretary", is_momo=True, window_id="w1",
        )
        result = await tool.__call__(
            template_id="pm-secretary",
            agent_id="dup-agent",
        )
        assert "已存在" in result
        print(f"  ✅ duplicate rejected: {result[:60]}...")
        ck("duplicate", True)
    except Exception as e:
        print(f"  ❌ duplicate: {e}")
        ck("duplicate", False)
    finally:
        teardown(root)

    # ── 5. Integration with build_openmox_tools ──
    try:
        root = setup()
        dao = ConfigDAO(root)
        # Register momo
        dao.create_agent(agent_id="momo", template_id="pm-secretary", name="秘书")
        dao.set_momo("momo")

        from src.core.openmox_toolkit import build_openmox_tools
        kit = build_openmox_tools(dao=dao, agent_id="momo", window_id="w1")

        # momo should get AgentFromTemplateTool
        names = [t.name for t in kit["extra_tools"]]
        assert "agent_from_template" in names, f"missing tool, got {names}"
        assert "update_dashboard" in names
        assert "create_task_plan" in names
        print(f"  ✅ integrated in toolkit: {names}")
        ck("integration", True)
    except Exception as e:
        print(f"  ❌ integration: {e}")
        ck("integration", False)
    finally:
        teardown(root)

    # ── 6. Non-momo doesn't get the tool ──
    try:
        root = setup()
        dao = ConfigDAO(root)
        dao.create_agent(agent_id="momo", template_id="pm-secretary", name="秘书")
        dao.set_momo("momo")
        dao.create_agent(agent_id="pd", template_id="product-manager", name="产品")

        from src.core.openmox_toolkit import build_openmox_tools
        kit = build_openmox_tools(dao=dao, agent_id="pd", window_id="w1")

        names = [t.name for t in kit["extra_tools"]]
        assert "agent_from_template" not in names, f"PD should not get this tool, got {names}"
        assert "update_dashboard" in names  # everyone gets this
        print(f"  ✅ PD toolkit (no agent_from_template): {names}")
        ck("no_tool_for_pd", True)
    except Exception as e:
        print(f"  ❌ no_tool_for_pd: {e}")
        ck("no_tool_for_pd", False)
    finally:
        teardown(root)

    print("=" * 50)
    passed = sum(1 for _, r in results if r == "✅")
    print(f"Results: {passed}/{len(results)}")
    for name, status in results:
        print(f"  {status} {name}")
    if passed < len(results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

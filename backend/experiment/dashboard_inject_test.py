"""Experiment: verify OnboardingMiddleware injects formatted dashboard.

Run: cd backend && .venv/bin/python experiment/dashboard_inject_test.py
"""

import os, sys, shutil, tempfile
from pathlib import Path

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BACKEND_DIR, "agentscope", "src"))
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from src.dao.dashboard_dao import DashboardDAO
from src.core.agent_factory import OnboardingMiddleware


def setup():
    root = Path(tempfile.mkdtemp(prefix="mox_inj_"))
    (root / ".Project").mkdir(parents=True, exist_ok=True)
    return root


def teardown(root: Path):
    if root.exists():
        shutil.rmtree(str(root), ignore_errors=True)


def test_static_only():
    """Static onboarding without dashboard."""
    mw = OnboardingMiddleware(onboarding_context="项目: 博客系统\n要求: 中文")
    # on_system_prompt is async, but it's pure synchronous logic
    import asyncio
    prompt = asyncio.run(mw.on_system_prompt(None, "你是一个产品经理"))
    assert "项目背景" in prompt
    assert "博客系统" in prompt
    assert "你的任务看板" not in prompt  # no dashboard
    print("  ✅ static only: onboarding present, dashboard absent")


def test_dashboard_formatting():
    """Dashboard with mixed task statuses → formatted correctly."""
    root = setup()
    try:
        dao = DashboardDAO(root)
        dao.create_task(title="可开始任务", owner="product-manager")
        t2 = dao.create_task(title="进行中任务", owner="product-manager")
        dao.update_task(t2.id, status="in_progress")
        t3 = dao.create_task(title="等待任务", owner="product-manager",
                             depends_on=["task-xxx"])
        t4 = dao.create_task(title="阻塞任务", owner="product-manager")
        dao.update_task(t4.id, status="blocked", blocked_reason="等资料")

        mw = OnboardingMiddleware(
            onboarding_context="项目背景",
            dashboard_dao=dao,
            window_id="w1",
        )
        import asyncio
        prompt = asyncio.run(mw.on_system_prompt(
            type("Agent", (), {"name": "product-manager"})(),
            "你是一个产品经理",
        ))

        assert "项目背景" in prompt
        assert "你的任务看板" in prompt
        assert "🟢 可开始" in prompt
        assert "可开始任务" in prompt
        assert "🟡 进行中" in prompt
        assert "进行中任务" in prompt
        assert "⏳ 等待前置" in prompt
        assert "等待任务" in prompt
        assert "🔴 阻塞" in prompt
        assert "阻塞任务" in prompt
        assert "等资料" in prompt
        print("  ✅ dashboard: 4 sections rendered correctly")
        print(f"    ~{len(prompt)} chars total")
    finally:
        teardown(root)


def test_empty_dashboard():
    """No tasks → no dashboard section."""
    root = setup()
    try:
        dao = DashboardDAO(root)
        mw = OnboardingMiddleware(
            onboarding_context="背景",
            dashboard_dao=dao,
            window_id="w1",
        )
        import asyncio
        prompt = asyncio.run(mw.on_system_prompt(
            type("Agent", (), {"name": "product-manager"})(),
            "你是一个产品经理",
        ))
        assert "你的任务看板" not in prompt
        print("  ✅ empty dashboard: no dashboard section injected")
    finally:
        teardown(root)


def test_window_filtering():
    """Tasks from other windows are excluded."""
    root = setup()
    try:
        dao = DashboardDAO(root)
        dao.create_task(title="窗口A任务", owner="PD", window_id="w1")
        dao.create_task(title="窗口B任务", owner="Dev", window_id="w2")
        dao.create_task(title="项目级任务", owner="Arch", window_id=None)

        # Agent in w1 should see w1 task + project task, NOT w2 task
        tasks = dao.get_tasks_for_agent("product-manager", "w1")
        mw = OnboardingMiddleware(dashboard_dao=dao, window_id="w1")
        import asyncio
        prompt = asyncio.run(mw.on_system_prompt(
            type("Agent", (), {"name": "product-manager"})(),
            "prompt",
        ))
        print(f"    prompt: {repr(prompt[:300])}")
        assert "窗口A任务" in prompt
        assert "项目级任务" in prompt
        assert "窗口B任务" not in prompt
        print("  ✅ window filtering: w1 agent sees w1 + project, not w2")
    finally:
        teardown(root)


def test_owner_gated_visibility():
    """An agent sees tasks assigned to them across windows."""
    root = setup()
    try:
        dao = DashboardDAO(root)
        dao.create_task(title="我的任务", owner="dev-manager", window_id="w2")
        dao.create_task(title="别人任务", owner="PD", window_id="w3")

        # Dev in w1 → should see "我的任务" (assigned to them) but NOT "别人任务"
        mw = OnboardingMiddleware(dashboard_dao=dao, window_id="w1")
        import asyncio
        prompt = asyncio.run(mw.on_system_prompt(
            type("Agent", (), {"name": "dev-manager"})(),
            "prompt",
        ))
        assert "我的任务" in prompt
        assert "别人任务" not in prompt
        print("  ✅ owner gating: Dev sees own cross-window task, not others'")
    finally:
        teardown(root)


def test_dashboard_unavailable_graceful():
    """Dashboard file missing or corrupted → no crash, no section."""
    root = setup()
    try:
        # No dashboard file at all
        mw = OnboardingMiddleware(
            onboarding_context="背景",
            dashboard_dao=DashboardDAO(root),
            window_id="w1",
        )
        import asyncio
        prompt = asyncio.run(mw.on_system_prompt(
            type("Agent", (), {"name": "PD"})(),
            "prompt",
        ))
        assert "你的任务看板" not in prompt
        print("  ✅ missing dashboard: graceful skip")
    finally:
        teardown(root)


if __name__ == "__main__":
    results = []
    for name, fn in [
        ("static_only", test_static_only),
        ("dashboard_format", test_dashboard_formatting),
        ("empty", test_empty_dashboard),
        ("window_filter", test_window_filtering),
        ("owner_gating", test_owner_gated_visibility),
        ("graceful", test_dashboard_unavailable_graceful),
    ]:
        try:
            fn()
            results.append((name, "✅"))
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            import traceback; traceback.print_exc()
            results.append((name, f"❌ {e}"))

    print("=" * 50)
    passed = sum(1 for _, r in results if r == "✅")
    print(f"Results: {passed}/{len(results)}")
    for name, status in results:
        print(f"  {status} {name}")
    if passed < len(results):
        sys.exit(1)

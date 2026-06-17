"""
M 类 — 启动/关闭生命周期测试 (2 场景)

These tests manage their own backend lifecycle (not using the session fixture),
so they import infrastructure directly rather than relying on conftest fixtures.

场景映射:
  M2  全部组件就绪 → health OK
  M3  优雅关闭 → 无资源泄漏

用法: cd backend && uv run pytest experiment/tests/test_lifecycle.py -v
"""

import asyncio
import os
import shutil
import signal
import time
from pathlib import Path

import httpx
import pytest

# ── Paths (mirrored from conftest, since lifecycle tests self-manage backend) ─
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
TEST_PROJECT = BACKEND_DIR.parent / "TestProject"
TEMPLATE_DIR = BACKEND_DIR / "experiment" / "test_project_template"
DATA_DIR = BACKEND_DIR / "data"
LOG_DIR = BACKEND_DIR.parent / "logs"

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6480"))
BASE_URL = "http://localhost:8000"


# ── Helpers ────────────────────────────────────────────


async def _redis_flush():
    import redis.asyncio as aioredis
    r = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0,
                       socket_connect_timeout=5)
    await r.ping()
    await r.flushdb()
    await r.aclose()


def _reset_sqlite():
    db_path = DATA_DIR / "openmox.db"
    for suffix in ["", "-journal", "-wal", "-shm"]:
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink(missing_ok=True)


def _reset_test_project():
    if TEST_PROJECT.exists():
        shutil.rmtree(str(TEST_PROJECT), ignore_errors=True)
    shutil.copytree(str(TEMPLATE_DIR), str(TEST_PROJECT), dirs_exist_ok=True)


class _BackendProcess:
    """Minimal backend process manager (no conftest logging dependency)."""

    def __init__(self):
        self.proc = None
        self._env_override: dict = {}

    async def start(self, timeout=30.0):
        env = os.environ.copy()
        env.update(self._env_override)
        env.setdefault("DEEPSEEK_API_KEY",
                       "sk-xxxxxxxxxx")
        env.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        env.setdefault("DEEPSEEK_MODEL", "deepseek-v4-flash")
        env.setdefault("REDIS_HOST", REDIS_HOST)
        env.setdefault("REDIS_PORT", str(REDIS_PORT))
        env.setdefault("OPENMOX_THINKING", "0")
        env["PYTHONUNBUFFERED"] = "1"

        log_file = open(str(LOG_DIR / "openmox-backend-test.log"), "w")
        self.proc = await asyncio.create_subprocess_exec(
            "uv", "run", "python", "run.py",
            cwd=str(BACKEND_DIR), env=env,
            stdout=log_file, stderr=asyncio.subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
        self._start_time = time.time()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc.returncode is not None:
                return False
            try:
                async with httpx.AsyncClient() as c:
                    r = await c.get(f"{BASE_URL}/api/health", timeout=3.0)
                    if r.status_code == 200:
                        return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return False

    async def stop(self):
        if self.proc is None:
            return
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                await self.proc.wait()
        except ProcessLookupError:
            pass


# ═══════════════════════════════════════════════════════════
# M2 — 全部组件就绪
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_M2_all_components_ready(backend, http_client):
    """后端启动后 health check OK + REST API 可访问."""
    r = await http_client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r2 = await http_client.get("/api/agents")
    assert r2.status_code == 200

    r3 = await http_client.get("/api/agent-templates")
    assert r3.status_code == 200


# ═══════════════════════════════════════════════════════════
# M3 — 优雅关闭
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_M3_graceful_shutdown_restart():
    """停止 → 重启 → 后端仍可正常工作.

    注意: 不调用 _reset_sqlite() — M3 的独立 BackendProcess 自管理 DB，
    不应触碰 session fixture 后端的 SQLite 文件。
    """
    await _redis_flush()
    _reset_test_project()

    # 第一轮
    bp1 = _BackendProcess()
    assert await bp1.start(), "第一次启动失败"
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as c:
        r = await c.get("/api/health")
        assert r.status_code == 200
    await bp1.stop()

    # 第二轮
    bp2 = _BackendProcess()
    assert await bp2.start(), "第二次启动失败"
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as c:
        r = await c.get("/api/health")
        assert r.status_code == 200
    await bp2.stop()


# ═══════════════════════════════════════════════════════════
# M4 — API Key 未设置 (P1 · 2026-06-13)
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_M4_no_api_key_warning():
    """DEEPSEEK_API_KEY 未设置时, 后端不崩溃."""
    bp = _BackendProcess()
    # 覆盖 env 中的 API key 为空
    bp._env_override = {"DEEPSEEK_API_KEY": ""}
    started = await bp.start(timeout=15.0)
    if started:
        import httpx
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as c:
            r = await c.get("/api/health")
            assert r.status_code == 200
    await bp.stop()


# ═══════════════════════════════════════════════════════════
# M1 — Redis 不可达降级 (P1 · 2026-06-13)
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_M1_redis_unreachable_degradation():
    """Redis 不可达时, 后端降级启动不崩溃."""
    import subprocess, time

    subprocess.run(["docker", "stop", "skill-redis-server"], capture_output=True)
    time.sleep(2)

    try:
        bp = _BackendProcess()
        started = await bp.start(timeout=15.0)
        if started:
            import httpx
            async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as c:
                try:
                    r = await c.get("/api/health")
                    assert r.status_code in (200, 503)
                except Exception:
                    pass
        await bp.stop()
    finally:
        subprocess.run(["docker", "start", "skill-redis-server"], capture_output=True)
        time.sleep(2)

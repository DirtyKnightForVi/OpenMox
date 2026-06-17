"""
Shared test fixtures for OpenMox E2E test suite.

Usage: cd backend && uv run pytest experiment/tests/ -v

This module imports core utilities from _helpers.py and adds:
  - Logging wrappers (test runner log + backend log tail)
  - pytest fixtures (backend process, ws_client, http_client)
  - pytest hooks (test pass/fail logging, event dump on failure)

DO NOT import from conftest directly — use _helpers for shared utilities.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import signal
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import pytest
import pytest_asyncio
import httpx

# ── Import core utilities from _helpers ──────────────

from ._helpers import (
    EventCollector,
    make_command,
    ws_connect as _ws_connect,
    ws_send_and_collect as _ws_send_and_collect,
    BACKEND_DIR,
    TEST_PROJECT,
    TEMPLATE_DIR,
    LOG_DIR,
    BASE_URL,
    REDIS_HOST,
    REDIS_PORT,
)

# ═══════════════════════════════════════════════════════════
# Test logger
# ═══════════════════════════════════════════════════════════

DATA_DIR = BACKEND_DIR / "data"
TEST_LOG_PATH = LOG_DIR / "openmox-test-runner.log"
_BACKEND_LOG = LOG_DIR / "openmox-backend-test.log"

_test_logger: logging.Logger | None = None


def _setup_test_logger() -> logging.Logger:
    global _test_logger
    if _test_logger is not None:
        return _test_logger
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("openmox.test")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    fh = logging.FileHandler(str(TEST_LOG_PATH), encoding="utf-8", mode="w")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    _test_logger = logger
    return logger


def get_log() -> logging.Logger:
    return _setup_test_logger()


def _tail_backend_log(lines: int = 40) -> str:
    if not _BACKEND_LOG.exists():
        return "(backend log not found)"
    try:
        with open(_BACKEND_LOG, encoding="utf-8") as f:
            all_lines = f.readlines()
        return "".join(all_lines[-lines:])
    except Exception:
        return "(cannot read backend log)"


# ═══════════════════════════════════════════════════════════
# Redis / SQLite / TestProject helpers
# ═══════════════════════════════════════════════════════════


async def redis_flush() -> bool:
    log = get_log()
    try:
        import redis.asyncio as aioredis
        r = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0,
                           socket_connect_timeout=5)
        await r.ping()
        await r.flushdb()
        await r.aclose()
        log.info("Redis flushed (localhost:%s)", REDIS_PORT)
        return True
    except Exception as e:
        log.warning("Redis flush failed: %s", e)
        return False


async def redis_ping() -> bool:
    try:
        import redis.asyncio as aioredis
        r = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                           socket_connect_timeout=3)
        await r.ping()
        await r.aclose()
        return True
    except Exception:
        return False


def reset_test_project() -> bool:
    log = get_log()
    if TEST_PROJECT.exists():
        shutil.rmtree(str(TEST_PROJECT), ignore_errors=True)
    try:
        shutil.copytree(str(TEMPLATE_DIR), str(TEST_PROJECT),
                        dirs_exist_ok=True)
        log.info("TestProject rebuilt from template")
        return True
    except Exception as e:
        log.error("TestProject rebuild failed: %s", e)
        return False


def reset_sqlite() -> bool:
    log = get_log()
    db_path = DATA_DIR / "openmox.db"
    for suffix in ["", "-journal", "-wal", "-shm"]:
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink(missing_ok=True)
    log.info("SQLite reset")
    return True


# ═══════════════════════════════════════════════════════════
# Backend process
# ═══════════════════════════════════════════════════════════


class BackendProcess:
    """Manage uvicorn subprocess lifecycle."""

    def __init__(self):
        self.proc: Optional[asyncio.subprocess.Process] = None
        self._start_time: float = 0.0

    async def start(self, timeout: float = 30.0) -> bool:
        log = get_log()

        # ── Kill any stale process on port 8000 ──
        import subprocess
        try:
            result = subprocess.run(
                ["fuser", "-k", "8000/tcp"],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                log.info("Killed stale process on port 8000")
                time.sleep(1.0)
        except Exception:
            pass

        env = os.environ.copy()
        env.setdefault("DEEPSEEK_API_KEY",
                       "sk-xxxxxxxxxx")
        env.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        env.setdefault("DEEPSEEK_MODEL", "deepseek-v4-flash")
        env.setdefault("REDIS_HOST", REDIS_HOST)
        env.setdefault("REDIS_PORT", str(REDIS_PORT))
        env.setdefault("OPENMOX_THINKING", "0")
        env["PYTHONUNBUFFERED"] = "1"

        log.info("Starting backend: uv run python run.py (cwd=%s)", BACKEND_DIR)
        log_file = open(str(_BACKEND_LOG), "w")

        self.proc = await asyncio.create_subprocess_exec(
            "uv", "run", "python", "run.py",
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=log_file,
            stderr=asyncio.subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
        self._start_time = time.time()

        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc.returncode is not None:
                log.error("Backend exited prematurely (code=%s)",
                          self.proc.returncode)
                return False
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(f"{BASE_URL}/api/health", timeout=3.0)
                    if r.status_code == 200:
                        elapsed = time.time() - self._start_time
                        log.info("Backend ready in %.1fs (health=%s)",
                                 elapsed, r.json())
                        return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
        log.error("Backend start timed out after %.0fs", timeout)
        return False

    async def stop(self) -> None:
        log = get_log()
        if self.proc is None:
            return
        elapsed = time.time() - self._start_time
        log.info("Stopping backend (ran %.0fs)...", elapsed)
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                log.warning("Backend didn't stop, sending SIGKILL")
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                await self.proc.wait()
        except ProcessLookupError:
            pass
        log.info("Backend stopped")


# ═══════════════════════════════════════════════════════════
# WS helpers with logging (wrap _helpers versions)
# ═══════════════════════════════════════════════════════════


async def ws_connect(uri: str = "ws://localhost:8000/ws",
                     timeout: float = 10.0):
    """Connect WebSocket with logging."""
    log = get_log()
    log.info("WS connect → %s", uri)
    ws = await _ws_connect(uri, timeout)
    return ws


async def ws_send_and_collect(ws, msg: dict,
                               collect_until: str = "REPLY_END",
                               timeout: float = 120.0) -> EventCollector:
    """Send WS message with logging."""
    log = get_log()
    cmd = msg.get("command", "")[:60]
    log.info("WS send: %.60s", cmd)
    collector = await _ws_send_and_collect(
        ws, msg, collect_until, timeout,
    )
    log.info("WS collect done: %d events", len(collector.events))
    return collector


# ═══════════════════════════════════════════════════════════
# Session fixture: backend
# ═══════════════════════════════════════════════════════════


@pytest_asyncio.fixture(scope="session")
async def backend():
    log = get_log()
    log.info("=" * 60)
    log.info("TEST SESSION START")
    log.info("=" * 60)

    log.info("Pre-flight: checking Redis at %s:%s ...", REDIS_HOST, REDIS_PORT)
    if not await redis_ping():
        log.error("Redis not reachable")
        pytest.fail(f"Redis not reachable at {REDIS_HOST}:{REDIS_PORT}. "
                     "Start it: docker start skill-redis-server")
    log.info("Pre-flight: Redis OK")

    if not TEMPLATE_DIR.exists():
        log.error("Template dir missing: %s", TEMPLATE_DIR)
        pytest.fail(f"Template dir missing: {TEMPLATE_DIR}")
    log.info("Pre-flight: template dir OK (%s)", TEMPLATE_DIR)

    await redis_flush()
    reset_sqlite()
    reset_test_project()

    bp = BackendProcess()
    if not await bp.start():
        log.error("Backend failed to start — dumping backend log:")
        log.error(_tail_backend_log(80))
        pytest.fail("Backend failed to start")

    log.info("Backend fixture ready for tests")
    yield bp

    log.info("Tearing down backend...")
    await bp.stop()
    log.info("=" * 60)
    log.info("TEST SESSION END")
    log.info("=" * 60)


# ═══════════════════════════════════════════════════════════
# Function fixtures
# ═══════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def ws_client(backend):
    log = get_log()
    log.info("── WS client fixture: connecting ──")
    ws = await ws_connect()
    yield ws
    log.info("── WS client fixture: closing ──")
    try:
        await ws.close()
    except Exception as e:
        log.debug("WS close error (ignored): %s", e)


@pytest_asyncio.fixture
async def http_client(backend):
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        yield client


@pytest.fixture
def window_id():
    wid = f"test_{uuid.uuid4().hex[:8]}"
    get_log().debug("window_id: %s", wid)
    return wid


@pytest.fixture
def project_path():
    pp = str(TEST_PROJECT.resolve())
    get_log().debug("project_path: %s", pp)
    return pp


# ═══════════════════════════════════════════════════════════
# pytest hooks
# ═══════════════════════════════════════════════════════════


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        log = get_log()
        log.info("TEST %s: %s (%.2fs)",
                 "PASS" if report.passed else "FAIL",
                 item.nodeid, report.duration)
        if report.failed:
            log.error("TEST FAILED: %s", item.nodeid)
            log.error("Failure reason: %s",
                      report.longreprtext[:500]
                      if hasattr(report, 'longreprtext')
                      else str(report.longrepr)[:500])
            log.error("Backend log (last 40 lines):\n%s",
                      _tail_backend_log(40))
            try:
                for name, val in item.funcargs.items():
                    if isinstance(val, EventCollector):
                        log.error("Event dump:\n%s", val.dump())
            except Exception:
                pass

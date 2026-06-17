"""
OpenMox Backend -- FastAPI application entry point.

Start: cd backend && uv run python run.py

Architecture:
  main.py  →  src/  →  agentscope/ (local source, not pip package)

Uses AgentScope 2.0.1 infrastructure (RedisStorage, RedisMessageBus,
ChatService, WakeupDispatcher) via the standard lifespan pattern.
Custom WebSocket /ws and REST /api/* routes are registered on top.
"""

import os
from contextlib import asynccontextmanager, AsyncExitStack

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from src.core.logging import setup_logging, get_logger
from src.core.store import get_db, close_db
from src.schedule.scheduler import start_scheduler, stop_scheduler, scheduler as ap_scheduler
from src.core.dream_scheduler import _register_dream_jobs
from src.api.router import register_routers
from src.api.chat import handle_ws

# ── Logging (must be first) ────────────────────────────
setup_logging()
log = get_logger(__name__)


# ── Redis connection helpers ────────────────────────

def _redis_host() -> str:
    return os.environ.get("REDIS_HOST", "localhost")

def _redis_port() -> int:
    return int(os.environ.get("REDIS_PORT", "6480"))

def _redis_db() -> int:
    return int(os.environ.get("REDIS_DB", "0"))


# ── Lifespan (startup / shutdown) ──────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB + Redis-backed AgentScope infrastructure on startup,
    tear down on shutdown."""
    log.info("OpenMox starting...")
    await get_db()
    start_scheduler()
    _register_dream_jobs(ap_scheduler)

    # ── AgentScope infrastructure (standard lifespan pattern) ──
    async with AsyncExitStack() as stack:
        # ── Shared Redis connection pool (TCP keepalive) ──
        # Single pool for both Storage and MessageBus so Pub/Sub
        # subscribers (WakeupDispatcher, CancelDispatcher) survive
        # extended idle periods without TCP-level disconnection.
        try:
            import redis.asyncio as aioredis
            import socket
            redis_pool = aioredis.ConnectionPool(
                host=_redis_host(),
                port=_redis_port(),
                db=_redis_db(),
                decode_responses=True,
                socket_keepalive=True,
                socket_keepalive_options={
                    socket.TCP_KEEPIDLE: 60,
                    socket.TCP_KEEPINTVL: 10,
                    socket.TCP_KEEPCNT: 3,
                },
                socket_connect_timeout=10,
                socket_timeout=None,    # No timeout on idle reads (Pub/Sub)
                health_check_interval=30,
                max_connections=20,
            )
            # The pool is closed manually at shutdown below.
        except Exception:
            redis_pool = None
            log.warning("Cannot create shared Redis pool — falling back to per-service pools")

        conn_kwargs: dict = {}
        if redis_pool is not None:
            conn_kwargs["connection_pool"] = redis_pool

        # 1. Storage — Redis with agent CRUD bridged to ConfigDAO (YAML)
        from src.core.openmox_redis_storage import OpenMoxRedisStorage
        storage = OpenMoxRedisStorage(
            project_root=".",
            **conn_kwargs,
        )
        await stack.enter_async_context(storage)
        app.state.storage = storage
        log.info("Storage ready (Redis + ConfigDAO)")

        # 2. Message bus — Redis-backed (Stream + Pub/Sub + distributed lock)
        from agentscope.app.message_bus import RedisMessageBus
        message_bus = RedisMessageBus(**conn_kwargs)
        await stack.enter_async_context(message_bus)
        app.state.message_bus = message_bus
        log.info("MessageBus ready (Redis)")

        # 3. Workspace manager — all agents share the project root
        from src.core.openmox_workspace_manager import OpenMoxWorkspaceManager
        workspace_manager = await stack.enter_async_context(
            OpenMoxWorkspaceManager("."),
        )

        # 4. Background task manager — tracks offloaded long-running tools
        from agentscope.app._manager._background_task_manager import (
            BackgroundTaskManager,
        )
        bg_manager = await stack.enter_async_context(BackgroundTaskManager())
        app.state.background_task_manager = bg_manager

        # 5. ChatRunRegistry — per-process registry of in-flight chat-run tasks
        from agentscope.app._manager._chat_run_registry import ChatRunRegistry
        chat_run_registry = await stack.enter_async_context(ChatRunRegistry())
        app.state.chat_run_registry = chat_run_registry

        # 6. SchedulerManager — cron-based scheduled trigger
        from agentscope.app._manager._scheduler._scheduler_manager import (
            SchedulerManager,
        )
        scheduler = await stack.enter_async_context(
            SchedulerManager(storage=storage, message_bus=message_bus),
        )
        app.state.scheduler_manager = scheduler

        # 7. ChatService — canonical agent execution engine.
        #    extra_agent_tools: dashboard/call_agent/AgentFromTemplate tools.
        #    extra_agent_middlewares: factory-of-factory to capture message_bus
        #    for ContextSeedingMiddleware + WindowPublishMiddleware.
        from src.core.openmox_chat_service import OpenMoxChatService
        from src.core.openmox_toolkit import (
            make_tools_factory,
            make_middleware_factory,
        )
        # Capture storage + message_bus in a closure so the tools factory
        # (which ChatService calls with only user_id/agent_id/session_id)
        # can pass them through to tool constructors.
        tools_factory = make_tools_factory(
            storage=storage,
            message_bus=message_bus,
        )
        # Capture message_bus + project_root in a closure so the middleware
        # factory (which ChatService calls with only user_id/agent_id/session_id)
        # can inject message_bus into ContextSeedingMiddleware and
        # WindowPublishMiddleware.
        middleware_factory = make_middleware_factory(
            message_bus=message_bus,
            project_root=".",
        )
        chat_service = OpenMoxChatService(
            storage=storage,
            workspace_manager=workspace_manager,
            scheduler_manager=scheduler,
            background_task_manager=bg_manager,
            message_bus=message_bus,
            extra_agent_tools=tools_factory,
            extra_agent_middlewares=middleware_factory,
        )
        app.state.chat_service = chat_service
        app.state.chat_run_registry = chat_run_registry

        # 8. RetryableWakeupDispatcher — drains wake-up queue with retry
        from src.core.dispatcher_retry import RetryableWakeupDispatcher
        await stack.enter_async_context(
            RetryableWakeupDispatcher(
                message_bus=message_bus,
                storage=storage,
                chat_service=chat_service,
                chat_run_registry=chat_run_registry,
            ),
        )

        # 9. RetryableCancelDispatcher — cross-process chat-run cancellation with retry
        from src.core.dispatcher_retry import RetryableCancelDispatcher
        await stack.enter_async_context(
            RetryableCancelDispatcher(
                message_bus=message_bus,
                registry=chat_run_registry,
                bg_manager=bg_manager,
            ),
        )

        log.info("Agent Team infrastructure started (Redis + ChatService + WakeupDispatcher)")

        yield

        # Shutdown via AsyncExitStack (LIFO):
        # CancelDispatcher → WakeupDispatcher → ChatRunRegistry → SchedulerManager
        # → BackgroundTaskManager → WorkspaceManager → MessageBus → Storage
        log.info("Agent Team infrastructure shut down")

        # ── Close shared Redis pool ──
        if redis_pool is not None:
            try:
                await redis_pool.aclose()
                log.info("Redis connection pool closed")
            except Exception:
                pass

    stop_scheduler()
    await close_db()
    log.info("OpenMox stopped")


# ── App factory ────────────────────────────────────────


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI(
        title="OpenMox",
        version="0.1.0",
        description="Enterprise Multi-Agent Collaborative Platform",
        lifespan=lifespan,
    )

    # CORS — allow frontend dev server on any port
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── WebSocket endpoint ─
    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await handle_ws(ws)

    # ── REST API routes ─
    register_routers(app)

    # ── Health check ─
    @app.get("/api/health")
    async def health():
        """Return infrastructure metrics."""
        from src.core.ws_registry import active_sessions
        sessions = await active_sessions()
        return {
            "status": "ok",
            "ws_sessions": len(sessions),
        }

    log.info("Routes registered")
    return app


app = create_app()

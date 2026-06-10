"""
Unified router — registers all API sub-routers onto the FastAPI app.

Imported by main.py's create_app().
"""

from fastapi import FastAPI

from .agents import router as agents_router
from .projects import router as projects_router
from .sessions import router as sessions_router
from .config import router as config_router
from .schedules import router as schedules_router
from .dashboard import router as dashboard_router
from .memory import router as memory_router
from .fs import router as fs_router


def register_routers(app: FastAPI) -> None:
    """Register all REST routers on the FastAPI app.

    Note: WebSocket /ws is registered directly in main.py because
    FastAPI WebSocket routes must be on the app, not an APIRouter.
    """
    app.include_router(agents_router)
    app.include_router(projects_router)
    app.include_router(sessions_router)
    app.include_router(config_router)
    app.include_router(schedules_router)
    app.include_router(dashboard_router)
    app.include_router(memory_router)
    app.include_router(fs_router)

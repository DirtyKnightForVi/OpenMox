"""
Filesystem browsing endpoint — used by the frontend path picker to let
users navigate directories visually.
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from ..core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["fs"])


@router.get("/fs/ls")
async def fs_list(path: str = Query(default="/", description="Directory to list")):
    """Return sub‑directories under ``path``.

    Entries are sorted alphabetically with directories first (hidden
    entries excluded unless ``path`` itself is a hidden directory).
    """
    try:
        root = Path(path).expanduser().resolve()
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid path: {path}")

    if not root.exists():
        raise HTTPException(status_code=400, detail=f"Path not found: {root}")
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {root}")

    try:
        entries: list[dict] = []
        for child in sorted(root.iterdir()):
            if child.name.startswith("."):
                continue
            try:
                is_dir = child.is_dir()
            except OSError:
                continue
            if is_dir:
                entries.append({
                    "name": child.name,
                    "path": str(child),
                    "type": "dir",
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {root}")
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read directory: {exc}")

    return {
        "current": str(root),
        "parent": str(root.parent) if root.parent != root else None,
        "entries": entries,
    }

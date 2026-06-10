"""
OpenMox launcher — injects agentscope source into sys.path, then starts uvicorn.

Usage: cd backend && uv run python run.py

The key design decision: agentscope lives as LOCAL SOURCE under
backend/agentscope/src/ — NOT as a pip package in .venv.
This lets CodeGraph trace every reference from our src/ into agentscope/.
"""

import sys
import os
from pathlib import Path

# ── Ensure backend/ is the working directory ───────────
BACKEND_DIR = Path(__file__).resolve().parent
os.chdir(str(BACKEND_DIR))

# ── Inject agentscope source into sys.path ─────────────
# This MUST happen before any agentscope import.
# After this, `from agentscope.agent import Agent` resolves to
#   backend/agentscope/src/agentscope/agent/_agent.py
# CodeGraph can trace the full dependency chain.
AGENTSCOPE_SRC = BACKEND_DIR / "agentscope" / "src"
if not AGENTSCOPE_SRC.exists():
    print(f"ERROR: agentscope source not found at {AGENTSCOPE_SRC}")
    print("Clone it: git clone https://github.com/agentscope-ai/agentscope.git backend/agentscope")
    sys.exit(1)

sys.path.insert(0, str(AGENTSCOPE_SRC))

# ── Default environment variables ──────────────────────
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-6fae26aeffe643fdbe6a93f9edea1a58")
os.environ.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
os.environ.setdefault("DEEPSEEK_MODEL", "deepseek-v4-flash")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6480")
os.environ.setdefault("OPENMOX_THINKING", "0")  # 0=disabled, 1=enabled (deepseek-v4 reasoning mode)
os.environ.setdefault("OPENMOX_LOG_DIR", str(BACKEND_DIR.parent / "logs"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=os.environ.get("OPENMOX_RELOAD", "").lower() in ("1", "true", "yes"),
        reload_excludes=["data/*", "*.db", "*.db-journal", "__pycache__/*", "*.pyc"],
    )

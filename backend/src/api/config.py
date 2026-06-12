"""
Config endpoints — PilotDeck settings panel compatibility.

Endpoints:
  GET    /api/config              — get config (YAML raw + metadata)
  PUT    /api/config              — save config
  POST   /api/config/validate     — validate config (stub)
  POST   /api/config/reload       — reload config (stub)
  POST   /api/config/open         — open config file (stub)
  GET    /api/config/provider     — current provider info
  POST   /api/config/test-connection — test LLM API connection
"""

import os
from pathlib import Path
from fastapi import APIRouter, Request

from ..core.settings import get_settings
from ..core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["config"])

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BACKEND_DIR / "pilotdeck.yaml"


@router.get("/config")
async def get_config():
    """Return current config (PilotDeck compat)."""
    s = get_settings()
    # Never expose plaintext credentials via API response.
    api_key_value = "${DEEPSEEK_API_KEY}"
    raw = f"""schemaVersion: 1
model:
    providers:
        deepseek:
            protocol: openai
            url: {s.deepseek_base_url}
            apiKey: {api_key_value}
            models:
                {s.deepseek_model}: {{}}
agent:
    model: deepseek/{s.deepseek_model}
memory:
    enabled: false
router:
    enabled: false
"""
    return {
        "path": str(CONFIG_PATH),
        "raw": raw,
        "exists": CONFIG_PATH.exists(),
        "validation": {"valid": True, "errors": [], "warnings": []},
        "reload": None,
    }


@router.put("/config")
async def save_config(request: Request):
    body = await request.json()
    raw = body.get("raw", "")
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(raw, encoding="utf-8")
    log.info("Config saved: %d chars", len(raw))
    return {
        "path": str(CONFIG_PATH),
        "raw": raw,
        "exists": True,
        "validation": {"valid": True, "errors": [], "warnings": []},
        "reload": None,
    }


@router.post("/config/validate")
async def validate_config(request: Request):
    return {"valid": True, "errors": [], "warnings": []}


@router.post("/config/reload")
async def reload_config():
    return {"ok": True, "path": str(CONFIG_PATH)}


@router.post("/config/open")
async def open_config():
    return {"success": True, "path": str(CONFIG_PATH)}


@router.get("/config/provider")
async def config_provider():
    s = get_settings()
    return {"provider": "deepseek", "model": s.deepseek_model}


@router.post("/config/test-connection")
async def test_connection(request: Request):
    """Test the LLM API connection by making a simple chat request."""
    s = get_settings()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{s.deepseek_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {s.deepseek_api_key}"},
                json={
                    "model": s.deepseek_model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 10,
                },
            )
        if resp.status_code == 200:
            return {"ok": True}
        return {"ok": False, "error": f"API returned {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

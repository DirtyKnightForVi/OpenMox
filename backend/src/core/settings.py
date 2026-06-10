"""
OpenMox settings — environment variable loading with sensible defaults.

All configuration flows through this module. No hardcoded secrets.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    # ── DeepSeek / OpenAI-compatible provider ──────────
    deepseek_api_key: str = field(
        default_factory=lambda: os.environ.get(
            "DEEPSEEK_API_KEY", os.environ.get("OPENAI_API_KEY", "")
        )
    )
    deepseek_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "DEEPSEEK_BASE_URL", os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
        )
    )
    deepseek_model: str = field(
        default_factory=lambda: os.environ.get(
            "DEEPSEEK_MODEL", os.environ.get("OPENAI_MODEL", "deepseek-v4-flash")
        )
    )

    # ── Paths ──────────────────────────────────────────
    backend_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent
    )
    data_dir: Path = field(default_factory=lambda: Path("data"))
    agents_dir: Path = field(default_factory=lambda: Path("agents"))
    logs_dir: Path = field(default_factory=lambda: Path("logs"))

    # ── Server ─────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True

    # ── Database ───────────────────────────────────────
    db_path: str = "data/openmox.db"


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

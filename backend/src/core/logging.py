"""
Structured logging with trace-id support.

Every request gets a unique trace_id injected via contextvars,
so all log lines from the same request are correlated.

Logs go to both stderr and ``backend/logs/openmox.log`` (local dev).
In production, set ``OPENMOX_LOG_DIR`` to override the directory.
"""

import logging
import os
import sys
from contextvars import ContextVar
from pathlib import Path

# ── Trace ID context ───────────────────────────────────
_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")

# ── Logger cache ───────────────────────────────────────
_loggers: dict[str, logging.Logger] = {}


class TraceFormatter(logging.Formatter):
    """Formatter that injects trace_id into every log line."""

    def format(self, record: logging.LogRecord) -> str:
        record.trace_id = _trace_id.get()[:8]  # short trace id
        return super().format(record)


def setup_logging(level: int = logging.DEBUG) -> None:
    """Configure root logger with structured format. Idempotent."""
    root = logging.getLogger()
    if root.handlers:
        return  # already set up

    fmt = TraceFormatter(
        "[%(asctime)s] %(levelname)-5s %(name)s [%(trace_id)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # ── stderr handler (always) ────────────
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(fmt)
    root.addHandler(stderr_handler)

    # ── File handler (local dev · auto-rotate) ──
    log_dir = Path(os.environ.get("OPENMOX_LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    # single-file mode — use a WatchedFileHandler so logrotate-friendly
    log_path = log_dir / "openmox-backend.log"
    try:
        fh = logging.FileHandler(str(log_path), encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass  # silently skip if file isn't writable

    root.setLevel(level)

    # Quiet noisy third-party loggers
    for name in ("httpx", "httpcore", "openai", "urllib3", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a cached logger for the given module name."""
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)
    return _loggers[name]


class LogContext:
    """Context manager that sets trace_id for the duration of a block."""

    @staticmethod
    def set_trace_id() -> str:
        import uuid
        tid = uuid.uuid4().hex[:12]
        _trace_id.set(tid)
        return tid

    @staticmethod
    def get_trace_id() -> str:
        return _trace_id.get()

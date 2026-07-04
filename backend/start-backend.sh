#!/bin/bash
set -e
cd "$(dirname "$0")"

# Ensure logs directory exists
mkdir -p ../logs

# Quick check: is Redis reachable?
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6480}"
if command -v redis-cli &>/dev/null; then
  if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping &>/dev/null; then
    echo "[$(date)] ⚠️  Redis $REDIS_HOST:$REDIS_PORT not reachable — backend may fail to start"
  fi
fi

LOG="../logs/openmox-backend.log"
exec > "$LOG" 2>&1
echo "[$(date)] === Backend starting (uv run python run.py) ==="
exec uv run python run.py

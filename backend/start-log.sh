#!/bin/bash
set -e
cd "$(dirname "$0")"
mkdir -p ../logs
echo "[$(date)] Backend starting (log + terminal) — Ctrl-C to stop"
exec uv run python run.py 2>&1 | tee ../logs/backend.log

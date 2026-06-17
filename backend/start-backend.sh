#!/bin/bash
cd "$(dirname "$0")"
LOG="../logs/openmox-backend.log"
exec > "$LOG" 2>&1
echo "[$(date)] === Backend starting ==="
exec uv run python run.py

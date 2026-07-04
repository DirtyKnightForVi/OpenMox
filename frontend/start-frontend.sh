#!/bin/bash
set -e
cd "$(dirname "$0")"
mkdir -p ../logs
LOG="../logs/openmox-frontend.log"
exec > "$LOG" 2>&1
echo "[$(date)] === Frontend starting (npm run dev) ==="
exec npm run dev

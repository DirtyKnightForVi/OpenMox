#!/bin/bash
cd "$(dirname "$0")"
LOG="../logs/openmox-frontend.log"
exec > "$LOG" 2>&1
echo "[$(date)] === Frontend starting ==="
exec npm run dev

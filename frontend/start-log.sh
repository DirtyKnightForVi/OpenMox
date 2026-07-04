#!/bin/bash
set -e
cd "$(dirname "$0")"
mkdir -p ../logs
echo "[$(date)] Frontend starting (log + terminal) — Ctrl-C to stop"
exec npm run dev 2>&1 | tee ../logs/frontend.log

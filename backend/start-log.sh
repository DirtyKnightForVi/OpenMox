#!/bin/bash
cd "$(dirname "$0")"
exec uv run python run.py 2>&1 | tee ../logs/backend.log

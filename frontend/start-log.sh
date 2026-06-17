#!/bin/bash
cd "$(dirname "$0")"
exec npm run dev 2>&1 | tee ../logs/frontend.log

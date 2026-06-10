#!/usr/bin/env bash
# ============================================================
# OpenMox — 统一启动脚本
# 启动后端 (FastAPI + AgentScope + Redis) 和前端 (Next.js)
# 日志写入项目根目录 logs/
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

# 颜色
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        OpenMox 统一启动               ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
echo ""

# ── 检查 Redis ─────────────────────────
echo -ne "Redis (localhost:6480) ... "
if docker exec skill-redis-server redis-cli ping &>/dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}不可用 — 尝试启动容器${NC}"
    docker start skill-redis-server &>/dev/null || true
    sleep 2
    if docker exec skill-redis-server redis-cli ping &>/dev/null; then
        echo -e "  ${GREEN}Redis 已启动${NC}"
    else
        echo -e "  ${YELLOW}警告: Redis 未运行，后端可能启动失败${NC}"
    fi
fi

# ── 后端 ───────────────────────────────
echo ""
echo -e "${GREEN}▶ 启动后端 (port 8000)${NC}"
echo "  日志: logs/openmox-backend.log"
cd "$ROOT_DIR/backend"
uv run python run.py &
BACKEND_PID=$!

# ── 前端 ───────────────────────────────
echo ""
echo -e "${GREEN}▶ 启动前端 (port 3000)${NC}"
echo "  日志: logs/openmox-frontend.log"
cd "$ROOT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

cd "$ROOT_DIR"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}OpenMox 已启动${NC}"
echo "  后端:    http://localhost:8000"
echo "  前端:    http://localhost:3000"
echo "  日志目录: $LOG_DIR"
echo "  PID:     后端=$BACKEND_PID  前端=$FRONTEND_PID"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "按 Ctrl+C 停止所有服务"

# ── 等待中断信号 ───────────────────────
trap "echo ''; echo '正在停止...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

# 等待任一进程结束
wait -n $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
echo ""
echo "服务已停止"

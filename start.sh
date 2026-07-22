#!/bin/bash
# ============================================
# 格物心法 知识库 - 一键部署脚本
# 用法:
#   ./start.sh              # 开发模式（自服务静态文件）
#   ./start.sh production   # 生产模式（仅 API，配合 Nginx）
#   ./start.sh stop         # 停止服务
# ============================================
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROJECT_DIR/.server.pid"
LOG_FILE="$PROJECT_DIR/server.log"
DATA_FILE="$PROJECT_DIR/data/chapters.json"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

stop_server() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "${YELLOW}停止服务 (PID: $PID)...${NC}"
            kill "$PID"
            rm -f "$PID_FILE"
            echo -e "${GREEN}服务已停止${NC}"
        else
            echo -e "${YELLOW}PID 文件存在但进程已不存在，清理中...${NC}"
            rm -f "$PID_FILE"
        fi
    else
        echo -e "${YELLOW}没有运行中的服务${NC}"
    fi
}

start_server() {
    # 检查是否已在运行
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "${RED}服务已在运行 (PID: $PID)${NC}"
            echo "如需重启请先执行: ./start.sh stop"
            exit 1
        fi
    fi

    # 检查数据文件
    if [ ! -f "$DATA_FILE" ]; then
        echo -e "${YELLOW}数据文件不存在，正在从 PDF 提取...${NC}"
        python3 "$PROJECT_DIR/extract_pdfs.py"
    fi

    # 检查依赖
    if ! python3 -c "import fastapi" 2>/dev/null; then
        echo -e "${YELLOW}安装依赖...${NC}"
        pip3 install -r "$PROJECT_DIR/requirements.txt"
    fi

    cd "$PROJECT_DIR"

    if [ "$1" = "production" ]; then
        # 生产模式：仅 API，监听 127.0.0.1
        echo -e "${GREEN}启动生产模式 (仅 API)${NC}"
        export PRODUCTION=1
        nohup python3 server.py --production > "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        echo -e "API 地址: ${GREEN}http://127.0.0.1:8765${NC}"
        echo -e "Nginx 需配置反向代理到此地址"
        echo -e "日志: $LOG_FILE"
    else
        # 开发模式：自服务静态文件，监听所有地址
        echo -e "${GREEN}启动开发模式 (含静态文件)${NC}"
        nohup python3 server.py > "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        echo -e "访问地址: ${GREEN}http://localhost:8765${NC}"
        echo -e "日志: $LOG_FILE"
    fi

    echo -e "PID: $(cat $PID_FILE)"
}

# 主逻辑
case "${1:-start}" in
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 1
        start_server "${2:-start}"
        ;;
    status)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo -e "${GREEN}服务运行中 (PID: $PID)${NC}"
            else
                echo -e "${RED}服务未运行（PID 文件残留）${NC}"
            fi
        else
            echo -e "${RED}服务未运行${NC}"
        fi
        ;;
    *)
        start_server "$1"
        ;;
esac

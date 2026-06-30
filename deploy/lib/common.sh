#!/bin/bash
# ============================================================
# cross_env_manager · 公共工具库
# 提供统一的日志输出、错误处理、横幅打印
# ============================================================

# ---- 颜色常量 ----
if [ -t 1 ]; then
    COLOR_RESET='\033[0m'
    COLOR_RED='\033[31m'
    COLOR_GREEN='\033[32m'
    COLOR_YELLOW='\033[33m'
    COLOR_BLUE='\033[34m'
    COLOR_CYAN='\033[36m'
    COLOR_BOLD='\033[1m'
else
    COLOR_RESET=''
    COLOR_RED=''
    COLOR_GREEN=''
    COLOR_YELLOW=''
    COLOR_BLUE=''
    COLOR_CYAN=''
    COLOR_BOLD=''
fi

# ---- 日志函数 ----
log_info()  { echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} $*"; }
log_ok()    { echo -e "${COLOR_GREEN}[ OK ]${COLOR_RESET} $*"; }
log_warn()  { echo -e "${COLOR_YELLOW}[WARN]${COLOR_RESET} $*"; }
log_error() { echo -e "${COLOR_RED}[ERROR]${COLOR_RESET} $*"; }

die() {
    log_error "$*"
    exit 1
}

banner() {
    echo ""
    echo -e "${COLOR_CYAN}========================================${COLOR_RESET}"
    echo -e "${COLOR_BOLD}  $PROJECT_NAME · 离线部署${COLOR_RESET}"
    echo -e "${COLOR_CYAN}========================================${COLOR_RESET}"
    echo "项目: $PROJECT_NAME"
    echo "端口: $APP_PORT"
    echo "用户: $(whoami)"
    echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "${COLOR_CYAN}----------------------------------------${COLOR_RESET}"
}

# 步骤标题
step() {
    echo ""
    echo -e "${COLOR_BOLD}[$1]${COLOR_RESET} $2"
}

# 分隔线
hr() {
    echo -e "${COLOR_CYAN}========================================${COLOR_RESET}"
}

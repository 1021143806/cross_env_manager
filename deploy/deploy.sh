#!/bin/bash
# ============================================================
# cross_env_manager · 多平台离线部署入口
# 自动检测 OS + Python 版本，按需走平台专属安装策略
#
# 用法:
#   sudo ./deploy.sh             默认：部署 CEM + postlook（如果存在）
#   sudo ./deploy.sh --cem-only  仅部署 cross_env_manager
# ============================================================
set -euo pipefail

# ---- 参数解析 ----
DEPLOY_POSTLOOK=true
for arg in "$@"; do
    case "$arg" in
        --cem-only) DEPLOY_POSTLOOK=false ;;
        --help|-h)  echo "用法: sudo ./deploy.sh [--cem-only]" ; exit 0 ;;
        *)          echo "未知参数: $arg (可用: --cem-only)" ; exit 1 ;;
    esac
done

# ---- 定位部署目录 ----
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"

# 基础路径合法性校验（防止空变量导致的危险操作）
if [ -z "$DEPLOY_DIR" ] || [ -z "$PROJECT_DIR" ]; then
    echo "❌ 无法确定部署目录，拒绝执行"
    exit 1
fi

# ---- 加载配置文件 ----
CONF_FILE="$DEPLOY_DIR/deploy.conf"
if [ -f "$CONF_FILE" ]; then
    source "$CONF_FILE"
else
    echo "❌ 配置文件不存在: $CONF_FILE"
    exit 1
fi

# ---- 加载核心库 ----
source "$DEPLOY_DIR/lib/common.sh"
source "$DEPLOY_DIR/lib/detect.sh"
source "$DEPLOY_DIR/lib/python.sh"
source "$DEPLOY_DIR/lib/deps.sh"
source "$DEPLOY_DIR/lib/supervisor.sh"

# ============================================================
# 主流程
# ============================================================
# 部署模式提示
if [ "$DEPLOY_POSTLOOK" = "true" ]; then
    DEPLOY_MODE="CEM + postlook"
else
    DEPLOY_MODE="CEM (仅)"
fi

banner
echo -e "部署模式: ${COLOR_GREEN}${DEPLOY_MODE}${COLOR_RESET}"

# 1. 环境检测
detect_os
detect_python
detect_supervisor

# ---- 项目文件检查 ----
step "1.4" "检查项目文件..."
cd "$PROJECT_DIR"
if [ ! -f "app.py" ]; then
    die "未在项目根目录找到 app.py"
fi
log_ok "项目文件检查通过"

# 2. Python 环境准备
ensure_python
create_venv

# 3. mysql.connector → PyMySQL 自动修复
step "3.5" "检查 mysql.connector 兼容性..."
if grep -q "^[[:space:]]*import mysql\.connector" app.py || grep -q "^[[:space:]]*from mysql\.connector" app.py; then
    log_warn "app.py 中仍有未注释的 mysql.connector 引用，自动修复..."
    sed -i.bak '/^[[:space:]]*import mysql\.connector/s/^/# /' app.py
    sed -i.bak2 '/^[[:space:]]*from mysql\.connector/s/^/# /' app.py
    sed -i 's/mysql\.connector\.connect/pymysql.connect/g' app.py
    log_ok "mysql.connector → PyMySQL 修复完成（备份: app.py.bak）"
else
    log_ok "app.py 中无未注释的 mysql.connector 引用"
fi

# 4. 安装依赖
install_deps

# 5. Supervisor 配置与启动
configure_supervisor
start_service

# ============================================================
# 部署完成
# ============================================================
echo ""
hr
echo -e "${COLOR_GREEN}  $PROJECT_NAME 部署完成！${COLOR_RESET}"
hr
echo ""
echo "部署信息:"
echo "  操作系统:   ${OS_PRETTY:-$OS_ID}"
echo "  Python:     $PYTHON_VERSION ($PYTHON_ABI)"
echo "  项目目录:   $PROJECT_DIR"
echo "  虚拟环境:   $PROJECT_DIR/${VENV_DIR:-venv}/"
echo "  服务端口:   $APP_PORT"
echo "  Supervisor: ${SUPERVISOR_CONF:-N/A}"
echo ""
echo "访问地址:"
echo "  WebUI:      http://localhost:$APP_PORT"
echo "  健康检查:   http://localhost:$APP_PORT/actuator/health"
echo ""
echo "管理命令:"
echo "  查看状态:   supervisorctl status $PROJECT_NAME"
echo "  重启服务:   supervisorctl restart $PROJECT_NAME"
echo "  停止服务:   supervisorctl stop $PROJECT_NAME"
echo "  查看日志:   tail -f $PROJECT_DIR/${LOG_DIR:-logs}/${PROJECT_NAME}.log"
echo ""
echo "如果服务未通过 Supervisor 运行（直接启动模式）:"
echo "  pkill -f 'python.*app.py'  # 杀掉直接启动的进程"
echo "  sudo supervisorctl restart $PROJECT_NAME  # 转由 Supervisor 管理"
echo "  supervisorctl status $PROJECT_NAME       # 确认状态为 RUNNING"
echo ""

# ============================================================
# 部署 postlook（如果存在且未禁用）
# ============================================================
if [ "$DEPLOY_POSTLOOK" = "true" ]; then
    POSTLOOK_DEPLOY="$PROJECT_DIR/Plugin/postlook/deploy/deploy.sh"

    if [ -f "$POSTLOOK_DEPLOY" ]; then
        hr
        echo -e "${COLOR_BOLD}→ 开始部署 postlook...${COLOR_RESET}"
        echo ""
        # 子进程执行，环境隔离；失败不影响 CEM 部署结果
        bash "$POSTLOOK_DEPLOY" && log_ok "postlook 部署完成" || \
            log_warn "postlook 部署失败（非致命，CEM 已正常运行）"
        echo ""
        echo "postlook 管理命令:"
        echo "  查看状态:   supervisorctl status postlook"
        echo "  访问地址:   http://localhost:5011"
        echo "  查看日志:   tail -f /main/log/app/postlook.log"
    else
        log_info "未找到 postlook 部署脚本 ($POSTLOOK_DEPLOY)，跳过"
    fi
fi

hr

#!/bin/bash
# ============================================================
# postlook · 多平台离线部署入口
# 自动检测 OS + Python 版本，按需走平台专属安装策略
# ============================================================
set -euo pipefail

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
banner

# 1. 环境检测
detect_os
detect_python
detect_supervisor

# ---- 安全闸：OS 白名单校验 ----
# 阻止未知系统被误判后执行不合规的平台脚本
# 设置环境变量 BYPASS_OS_CHECK=1 可跳过此校验（风险自负）
readonly OS_ALLOWLIST=("openEuler" "centos" "debian" "ubuntu")
if [ "${BYPASS_OS_CHECK:-0}" != "1" ]; then
    _os_allowed=false
    for allowed in "${OS_ALLOWLIST[@]}"; do
        if [ "$OS_ID" = "$allowed" ]; then
            _os_allowed=true
            break
        fi
    done
    if [ "$_os_allowed" = "false" ]; then
        die "不支持的操作系统: $OS_ID ($OS_PRETTY)\n  \
支持的平台: ${OS_ALLOWLIST[*]}\n  \
如需强制部署，请执行: BYPASS_OS_CHECK=1 ./deploy.sh"
    fi
    log_ok "操作系统通过白名单校验: $OS_ID"
else
    log_warn "已跳过 OS 白名单校验 (BYPASS_OS_CHECK=1)，风险自负"
fi

# 2. 项目文件检查
step "1.4" "检查项目文件..."
cd "$PROJECT_DIR"
if [ ! -f "src/postlook/app.py" ]; then
    die "未在项目根目录找到 src/postlook/app.py"
fi
log_ok "项目文件检查通过"

# ---- 配置文件初始化 ----

# env.toml（旧版兼容，回退方案）
if [ ! -f "config/env.toml" ] || [ ! -s "config/env.toml" ]; then
    if [ -f "config/template/env.toml" ]; then
        cp config/template/env.toml config/env.toml
        log_ok "配置文件已从模板初始化: config/env.toml"
    fi
fi

# app.toml（主配置）
if [ ! -f "config/app.toml" ] || [ ! -s "config/app.toml" ]; then
    if [ -f "config/template/app.toml" ]; then
        cp config/template/app.toml config/app.toml
        log_ok "主配置已从模板初始化: config/app.toml"
    fi
fi

# rules.toml（规则配置）
if [ ! -f "config/rules.toml" ] || [ ! -s "config/rules.toml" ]; then
    if [ -f "config/template/rules.toml" ]; then
        cp config/template/rules.toml config/rules.toml
        log_ok "规则配置已从模板初始化: config/rules.toml"
    fi
fi

# ---- 配置文件权限修复 ----
# 确保运行用户对 config 目录有写权限（支持热更新）
if command -v chown &>/dev/null && [ -n "${SUPERVISOR_USER:-}" ]; then
    chown -R "$SUPERVISOR_USER" config/ 2>/dev/null && \
        log_ok "配置文件权限已设为 $SUPERVISOR_USER" || \
        log_warn "无法更改 config/ 所有者，热更新可能需要手动授权"
fi

# 3. Python 环境准备
ensure_python
create_venv

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
echo "  前端页面:   http://localhost:$APP_PORT"
echo "  API 文档:   http://localhost:$APP_PORT/docs"
echo "  健康检查:   http://localhost:$APP_PORT/api/health"
echo ""
echo "管理命令:"
echo "  查看状态:   supervisorctl status $PROJECT_NAME"
echo "  重启服务:   supervisorctl restart $PROJECT_NAME"
echo "  停止服务:   supervisorctl stop $PROJECT_NAME"
echo "  查看日志:   tail -f $LOG_PATH/${PROJECT_NAME}.log"
echo ""
echo "首次部署后配置初始化（热更新白名单）:"
echo "  curl -X POST http://localhost:\$APP_PORT/api/config \\"
echo '    -H "Content-Type: application/json" \'
echo '    -d @- << JSON'
echo '  {"content": "[server]\nhost = \"0.0.0.0\"\nport = 5011\n\n[logs]\nroot_dirs = [\"/var/log\", \"/main/app/ics/logs\", \"/main/app/tps/logs\"]\nmax_lines = 100\ndefault_lines = 50\ndefault_recent_files = 10\n\n[ui]\ntheme = \"dark\"\n"}'
echo "  JSON"
echo ""
echo "如果服务未通过 Supervisor 运行（直接启动模式）:"
echo "  pkill -f 'uvicorn.*postlook'  # 杀掉直接启动的进程"
echo "  sudo supervisorctl restart $PROJECT_NAME  # 转由 Supervisor 管理"
echo "  supervisorctl status $PROJECT_NAME       # 确认状态为 RUNNING"
echo ""
hr

#!/bin/bash
# ============================================================
# postlook · 平台检测库
# 检测操作系统、Python 版本、ABI 标签
# ============================================================
#
# 导出变量:
#   OS_ID           - 操作系统 ID（如 openEuler, centos, ubuntu）
#   OS_VERSION      - 主版本号（如 24, 7, 22）
#   OS_PRETTY       - 完整版本名
#   ARCH            - CPU 架构（x86_64, aarch64）
#   PYTHON3         - python3 可执行文件路径
#   PYTHON_VERSION  - Python 完整版本（如 3.11.6）
#   PYTHON_MAJOR    - 主版本号（3）
#   PYTHON_MINOR    - 次版本号（11）
#   PYTHON_ABI      - ABI 标签（cp311, cp39）
#   USE_SYSTEM_PYTHON - 是否使用系统 Python（true/false）
#

detect_os() {
    step "1.1" "检测操作系统..."

    if [ -f /etc/os-release ]; then
        OS_ID=$(grep -oP '^ID="?\K[^"]+' /etc/os-release | head -1)
        OS_VERSION=$(grep -oP '^VERSION_ID="?\K[^"]+' /etc/os-release | head -1 | cut -d. -f1)
        OS_PRETTY=$(grep -oP '^PRETTY_NAME="?\K[^"]+' /etc/os-release | head -1)
    elif [ -f /etc/redhat-release ]; then
        OS_ID="centos"
        OS_VERSION=$(grep -oP '[0-9]+' /etc/redhat-release | head -1)
        OS_PRETTY=$(cat /etc/redhat-release)
    elif [ -f /etc/debian_version ]; then
        OS_ID="debian"
        OS_VERSION=$(cat /etc/debian_version | cut -d. -f1)
        OS_PRETTY="Debian $OS_VERSION"
    else
        OS_ID="unknown"
        OS_VERSION="0"
        OS_PRETTY="Unknown Linux"
    fi

    ARCH=$(uname -m)

    log_info "操作系统: ${OS_PRETTY:-$OS_ID}"
    log_info "架构:     $ARCH"
    log_info "OS_ID:    $OS_ID (v$OS_VERSION)"

    # 规范化 OS_ID
    OS_ID_LOWER=$(echo "$OS_ID" | tr '[:upper:]' '[:lower:]')
    case "$OS_ID_LOWER" in
        openeuler|iraypleos) OS_ID="openEuler" ;;
        centos|rhel|fedora)  OS_ID="centos" ;;
        ubuntu|debian)       OS_ID="debian" ;;
    esac
}

detect_python() {
    step "1.2" "检测 Python 环境..."

    PYTHON3=""

    # 1. deploy.conf 指定了 PYTHON3_PATH
    if [ -n "${PYTHON3_PATH:-}" ] && [ -x "$PYTHON3_PATH" ]; then
        PYTHON3="$PYTHON3_PATH"
        log_info "使用配置指定的 Python: $PYTHON3_PATH"
    # 2. 系统默认 python3
    elif command -v python3 &>/dev/null; then
        PYTHON3="$(command -v python3)"
    # 3. CentOS 7 SCL
    elif [ -x "/opt/rh/rh-python39/root/bin/python3" ]; then
        PYTHON3="/opt/rh/rh-python39/root/bin/python3"
    # 4. 通用路径
    elif [ -x "/usr/local/bin/python3" ]; then
        PYTHON3="/usr/local/bin/python3"
    elif [ -x "/usr/local/python3/bin/python3" ]; then
        PYTHON3="/usr/local/python3/bin/python3"
    fi

    if [ -z "$PYTHON3" ]; then
        USE_SYSTEM_PYTHON=false
        log_warn "未找到系统 python3"
        return
    fi

    PYTHON_VERSION=$($PYTHON3 --version 2>&1 | grep -oP '[0-9]+\.[0-9]+\.[0-9]+')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    PYTHON_ABI="cp$PYTHON_MAJOR$PYTHON_MINOR"

    log_info "Python 路径:    $PYTHON3"
    log_info "Python 版本:    $PYTHON_VERSION"
    log_info "Python ABI:     $PYTHON_ABI"

    # 检查版本是否满足 >= 3.9
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 9 ]; then
        USE_SYSTEM_PYTHON=true
        log_ok "系统 Python $PYTHON_VERSION 满足要求 (>= 3.9)"
    else
        USE_SYSTEM_PYTHON=false
        log_warn "系统 Python $PYTHON_VERSION 不满足要求 (需要 >= 3.9)"
    fi
}

detect_supervisor() {
    step "1.3" "检测 Supervisor..."

    if command -v supervisorctl &>/dev/null; then
        SUPERVISOR_AVAILABLE=true
        log_ok "supervisorctl 可用"
    else
        SUPERVISOR_AVAILABLE=false
        log_warn "supervisorctl 不可用，将使用直接启动方式"
    fi
}

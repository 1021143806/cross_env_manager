#!/bin/bash
# ============================================================
# postlook · Python 环境准备
# 确保 Python 3.9+ 可用，创建虚拟环境
# ============================================================

# ---- 安全工具：受控删除目录 ----
# 仅在路径非空、且路径位于项目目录内时才允许 rm -rf
_safe_rm_dir() {
    local target="$1"
    local desc="$2"

    if [ -z "$target" ]; then
        die "内部错误: _safe_rm_dir 收到空路径 ($desc)"
    fi

    # 拒绝删除根目录、/usr、/etc 等系统关键路径
    case "$target" in
        /|/usr|/usr/*|/etc|/etc/*|/bin|/sbin|/lib|/lib64|/var|/var/*|/home|/root|/opt|/tmp|/main)
            die "安全拒绝: 不允许删除系统关键路径: $target ($desc)"
            ;;
    esac

    # 路径必须位于项目目录下
    if [[ "$target" != "$PROJECT_DIR"/* ]]; then
        die "安全拒绝: 路径不在项目目录内: $target ($desc)"
    fi

    log_info "清理: $target ($desc)"
    rm -rf "$target"
}

# ---- 确保 Python 3.9+ 可用 ----
ensure_python() {
    step "2" "准备 Python 环境"

    # 如果系统 Python 已满足要求，直接使用
    if [ "${USE_SYSTEM_PYTHON:-false}" = "true" ]; then
        log_ok "使用系统 Python: $PYTHON3 ($PYTHON_VERSION)"
        return 0
    fi

    log_info "系统 Python 不满足要求，尝试平台专属方案..."

    # 按平台走不同的 Python 安装策略
    case "$OS_ID" in
        centos)
            if [ "$OS_VERSION" = "7" ]; then
                log_info "检测到 CentOS 7，执行专属 Python 安装..."
                if [ -f "$DEPLOY_DIR/platform/centos7/setup.sh" ]; then
                    source "$DEPLOY_DIR/platform/centos7/setup.sh"
                else
                    die "CentOS 7 安装脚本缺失: platform/centos7/setup.sh"
                fi
            else
                die "CentOS $OS_VERSION: 请手动安装 Python 3.9+ 或设置 PYTHON3_PATH"
            fi
            ;;
        openEuler)
            # openEuler 一般都自带 Python 3.9+，到这里说明没检测到
            die "openEuler 系统未检测到 Python 3，请检查安装: dnf install -y python3"
            ;;
        debian)
            die "Debian/Ubuntu 系统请先安装 Python 3.9+: apt install -y python3 python3-venv"
            ;;
        *)
            die "未知操作系统 ($OS_ID)，请手动安装 Python 3.9+ 或设置 PYTHON3_PATH"
            ;;
    esac

    # 重新检测 platform setup 后的 Python
    detect_python
    if [ "${USE_SYSTEM_PYTHON:-false}" != "true" ]; then
        die "Python 环境准备失败，无法继续"
    fi
}

# ---- 创建虚拟环境 ----
create_venv() {
    step "3" "创建虚拟环境"

    VENV_PATH="$PROJECT_DIR/${VENV_DIR:-venv}"

    # 校验 VENV_PATH 合法性
    if [ -z "${VENV_DIR:-}" ]; then
        die "VENV_DIR 未配置，拒绝删除操作"
    fi

    # 先删除旧 venv（使用安全函数）
    if [ -d "$VENV_PATH" ]; then
        _safe_rm_dir "$VENV_PATH" "旧虚拟环境"
    fi

    # 检查 venv 模块是否可用
    if ! $PYTHON3 -m venv --help &>/dev/null; then
        log_warn "venv 模块不可用，尝试安装..."
        case "$OS_ID" in
            centos|openEuler)
                log_info "尝试: dnf install -y python3-venv"
                dnf install -y python3-venv 2>/dev/null || true
                ;;
            debian)
                log_info "尝试: apt install -y python3-venv"
                apt install -y python3-venv 2>/dev/null || true
                ;;
        esac
    fi

    $PYTHON3 -m venv "$VENV_PATH" || die "虚拟环境创建失败"

    if [ ! -f "$VENV_PATH/bin/python" ]; then
        die "虚拟环境创建失败: $VENV_PATH/bin/python 不存在"
    fi

    log_ok "虚拟环境创建成功: $VENV_PATH"
    log_info "Python: $($VENV_PATH/bin/python --version 2>&1)"
}

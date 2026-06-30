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

    # 直接验证 platform 脚本设置的 PYTHON3（不重新调用 detect_python 避免覆盖）
    if [ -z "${PYTHON3:-}" ] || [ ! -x "$PYTHON3" ]; then
        die "平台脚本未设置有效的 PYTHON3"
    fi

    PYTHON_VERSION=$($PYTHON3 --version 2>&1 | grep -oP '[0-9]+\.[0-9]+\.[0-9]+' || true)
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    PYTHON_ABI="cp$PYTHON_MAJOR$PYTHON_MINOR"

    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 9 ]; then
        USE_SYSTEM_PYTHON=true
        log_ok "平台 Python 安装成功: $PYTHON3 ($PYTHON_VERSION)"
    else
        die "平台安装的 Python 无法正常运行: $PYTHON3"
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

    # 如果 venv 已存在且包含有效的 python，跳过创建
    if [ -d "$VENV_PATH" ] && [ -f "$VENV_PATH/bin/python" ] && [ -f "$VENV_PATH/bin/pip" ]; then
        log_ok "虚拟环境已存在: $VENV_PATH，跳过创建"
        return 0
    fi

    # 先删除旧的无效 venv（使用安全函数）
    if [ -d "$VENV_PATH" ]; then
        log_warn "虚拟环境不完整（缺少 python/pip），重建..."
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

    # conda Python 环境：让 venv 继承系统站点包（如 pydantic_core）
    local venv_cfg="$VENV_PATH/pyvenv.cfg"
    if [ -f "$venv_cfg" ] && [ "${USE_SYSTEM_SITE_PACKAGES:-false}" = "true" ]; then
        # 移除 include-system-site-packages = false，改为 true
        sed -i 's/^include-system-site-packages = false/include-system-site-packages = true/' "$venv_cfg"
        log_ok "已启用系统站点包继承 (pydantic_core 等 conda 包可用)"
    fi

    if [ ! -f "$VENV_PATH/bin/python" ]; then
        die "虚拟环境创建失败: $VENV_PATH/bin/python 不存在"
    fi

    log_ok "虚拟环境创建成功: $VENV_PATH"
    log_info "Python: $($VENV_PATH/bin/python --version 2>&1)"
}

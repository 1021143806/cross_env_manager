#!/bin/bash
# ============================================================
# cross_env_manager · 离线依赖安装
# Flask 框架依赖，按 ABI 分层：vendor_packages/common/ + vendor_packages/cp39/
# ============================================================

# 关键包列表（用于检查完整性）
readonly KEY_PACKAGES=(
    "flask" "werkzeug" "jinja2" "markupsafe" "pymysql" "click"
    "itsdangerous" "dbutils" "flask_caching" "blinker" "tomli"
    "importlib_metadata" "paramiko" "yaml" "cryptography"
)

install_deps() {
    step "4" "检查离线依赖包"

    local VENV_PATH="$PROJECT_DIR/${VENV_DIR:-venv}"

    # 如果依赖已安装，跳过
    if [ -f "$VENV_PATH/bin/python" ]; then
        if "$VENV_PATH/bin/python" -c "import flask, pymysql" 2>/dev/null; then
            log_ok "依赖已安装，跳过离线安装"
            return 0
        fi
    fi

    local VENDOR_BASE="$DEPLOY_DIR/${VENDOR_DIR:-vendor_packages}"
    local VENDOR_COMMON="$VENDOR_BASE/common"
    local VENDOR_CP39="$VENDOR_BASE/cp39"

    if [ ! -d "$VENDOR_COMMON" ]; then
        die "离线包目录不存在: $VENDOR_COMMON"
    fi

    local COMMON_COUNT=$(find "$VENDOR_COMMON" -name "*.whl" 2>/dev/null | wc -l)
    local CP39_COUNT=0
    if [ -d "$VENDOR_CP39" ]; then
        CP39_COUNT=$(find "$VENDOR_CP39" -name "*.whl" 2>/dev/null | wc -l)
    fi

    log_info "通用包 (common/): $COMMON_COUNT 个 (py3-none-any)"
    log_info "ABI包  (cp39/):   $CP39_COUNT 个 (cp39 编译版)"

    # 检查关键包是否存在
    local MISSING_PKGS=()
    for pkg in "${KEY_PACKAGES[@]}"; do
        local found=$(find "$VENDOR_COMMON" "$VENDOR_CP39" -type f -iname "*${pkg}*.whl" 2>/dev/null | head -1)
        if [ -f "$found" ]; then
            log_ok "$pkg: $(basename "$found")"
        else
            log_error "缺少关键包: $pkg"
            MISSING_PKGS+=("$pkg")
        fi
    done

    if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
        die "离线依赖包不完整，缺少: ${MISSING_PKGS[*]}"
    fi

    # ---- 安装依赖 ----
    step "5" "安装离线依赖包"

    source "$VENV_PATH/bin/activate" || die "虚拟环境激活失败"
    log_info "虚拟环境 Python: $(python --version 2>&1)"

    # 合并所有 whl 路径作为 find-links
    local FIND_LINKS=()
    [ -d "$VENDOR_COMMON" ] && FIND_LINKS+=("$VENDOR_COMMON")
    [ -d "$VENDOR_CP39" ] && FIND_LINKS+=("$VENDOR_CP39")

    local LINKS_ARGS=""
    for link in "${FIND_LINKS[@]}"; do
        LINKS_ARGS="$LINKS_ARGS --find-links=$link"
    done

    log_info "从离线目录安装: ${FIND_LINKS[*]}"

    # ---- ABI 匹配校验：确认 markupsafe 的 cp 标签与当前 Python 匹配 ----
    if [ -d "$VENDOR_CP39" ] && [ "$CP39_COUNT" -gt 0 ]; then
        local first_abi_whl=$(find "$VENDOR_CP39" -name "*.whl" 2>/dev/null | head -1)
        if [ -f "$first_abi_whl" ]; then
            local whl_abi=$(basename "$first_abi_whl" | grep -oP 'cp[0-9]+' | head -1 || true)
            if [ "$whl_abi" != "$PYTHON_ABI" ]; then
                die "ABI 不匹配: vendor_packages/cp39/ 中的包标记为 ${whl_abi}，\n  \
但当前 Python 是 ${PYTHON_VERSION} (${PYTHON_ABI})\n  \
请下载正确的 ABI 包"
            fi
            log_ok "ABI 校验通过: whl=${whl_abi} == python=${PYTHON_ABI}"
        fi
    fi

    # 阶段 1：批量安装
    log_info "批量安装所有依赖..."
    if pip install --no-index $LINKS_ARGS -r "$VENDOR_BASE/requirements_py39_fixed.txt" 2>/dev/null; then
        log_ok "批量依赖安装成功"
    else
        # 阶段 2：逐个安装（降级策略）
        log_warn "批量安装失败，尝试逐个安装..."
        local fail_count=0
        for dir in "${FIND_LINKS[@]}"; do
            for whl in "$dir"/*.whl; do
                [ -f "$whl" ] || continue
                local pkg_name=$(basename "$whl" | cut -d- -f1)
                if pip install --no-index --no-deps "$whl" 2>/dev/null; then
                    log_ok "$pkg_name"
                else
                    # 带依赖重试
                    if pip install --no-index $LINKS_ARGS "$whl" 2>/dev/null; then
                        log_ok "$pkg_name (带依赖)"
                    else
                        log_error "$pkg_name 安装失败"
                        fail_count=$((fail_count + 1))
                    fi
                fi
            done
        done
        if [ "$fail_count" -gt 0 ]; then
            die "$fail_count 个包安装失败"
        fi
    fi

    # ---- 验证安装 ----
    step "6" "验证安装"

    local VERIFY_PKGS=("flask" "pymysql" "werkzeug" "jinja2" "markupsafe" "importlib_metadata" "paramiko" "yaml" "cryptography" "dbutils")
    local ALL_OK=true

    for pkg in "${VERIFY_PKGS[@]}"; do
        if python -c "import $pkg; print('   ✅ $pkg')" 2>/dev/null; then
            :
        else
            log_error "$pkg 导入失败"
            ALL_OK=false
        fi
    done

    if [ "$ALL_OK" = "false" ]; then
        die "依赖安装验证失败"
    fi
    log_ok "关键包导入验证全部通过"

    deactivate 2>/dev/null || true
}

#!/bin/bash
# ============================================================
# postlook · 离线依赖安装
# ABI 感知：按 Python 版本选择对应的 vendor 子目录
# ============================================================

# 关键包列表（用于检查完整性）
readonly KEY_PACKAGES=("fastapi" "uvicorn" "pydantic" "starlette" "anyio" "pydantic_core" "typing_extensions" "tomli")

install_deps() {
    step "4" "检查离线依赖包"

    local VENV_PATH="$PROJECT_DIR/${VENV_DIR:-venv}"

    # 如果依赖已安装，跳过
    if [ -f "$VENV_PATH/bin/python" ]; then
        if "$VENV_PATH/bin/python" -c "import fastapi,uvicorn" 2>/dev/null; then
            log_ok "依赖已安装，跳过离线安装"
            return 0
        fi
    fi

    local VENDOR_BASE="$PROJECT_DIR/${VENDOR_DIR:-deploy/vendor_packages}"
    local VENDOR_COMMON="$VENDOR_BASE/common"
    local VENDOR_ABI="$VENDOR_BASE/${PYTHON_ABI}"

    if [ ! -d "$VENDOR_COMMON" ]; then
        die "离线包目录不存在: $VENDOR_COMMON"
    fi

    local COMMON_COUNT=$(find "$VENDOR_COMMON" -name "*.whl" 2>/dev/null | wc -l)
    local ABI_COUNT=0
    if [ -d "$VENDOR_ABI" ]; then
        ABI_COUNT=$(find "$VENDOR_ABI" -name "*.whl" 2>/dev/null | wc -l)
    fi

    log_info "通用包 (common/): $COMMON_COUNT 个"
    log_info "ABI包 (${PYTHON_ABI}/): $ABI_COUNT 个"

    # 检查关键包是否存在（在 common 或 abi 目录中）
    local MISSING_PKGS=()
    for pkg in "${KEY_PACKAGES[@]}"; do
        # pydantic_core 在 conda 环境中由系统站点包提供，跳过 vendor 检查
        if [ "$pkg" = "pydantic_core" ] && [ "${USE_SYSTEM_SITE_PACKAGES:-false}" = "true" ]; then
            log_ok "$pkg: 由 conda 系统站点包提供（跳过 vendor 检查）"
            continue
        fi
        local found=$(find "$VENDOR_COMMON" "$VENDOR_ABI" -type f -iname "*${pkg}*.whl" 2>/dev/null | head -1)
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

    # ---- 激活虚拟环境 ----
    step "5" "安装离线依赖包"

    local VENV_PATH="$PROJECT_DIR/${VENV_DIR:-venv}"
    source "$VENV_PATH/bin/activate" || die "虚拟环境激活失败"
    log_info "虚拟环境 Python: $(python --version 2>&1)"

    # 合并所有 whl 路径作为 find-links
    local FIND_LINKS=()
    [ -d "$VENDOR_COMMON" ] && FIND_LINKS+=("$VENDOR_COMMON")
    [ -d "$VENDOR_ABI" ] && FIND_LINKS+=("$VENDOR_ABI")

    local LINKS_ARGS=""
    for link in "${FIND_LINKS[@]}"; do
        LINKS_ARGS="$LINKS_ARGS --find-links=$link"
    done

    log_info "从离线目录安装: ${FIND_LINKS[*]}"

    # ---- ABI 匹配校验：安装前确认 ABI 包与当前 Python 匹配 ----
    # conda 环境跳过 ABI 校验（pydantic_core 由系统站点包提供）
    if [ "${USE_SYSTEM_SITE_PACKAGES:-false}" = "true" ]; then
        log_ok "conda 环境，跳过 ABI 校验（pydantic_core 由系统站点包提供）"
    elif [ -d "$VENDOR_ABI" ] && [ "$ABI_COUNT" -gt 0 ]; then
        local first_abi_whl=$(find "$VENDOR_ABI" -name "*.whl" 2>/dev/null | head -1)
        if [ -f "$first_abi_whl" ]; then
            # 从文件名提取 ABI 标签，如 pydantic_core-2.46.4-cp311-cp311-manylinux... → cp311
            local whl_abi=$(basename "$first_abi_whl" | grep -oP 'cp[0-9]+' | head -1 || true)
            if [ "$whl_abi" != "$PYTHON_ABI" ]; then
                die "ABI 不匹配: vendor_packages/${PYTHON_ABI}/ 中的包标记为 ${whl_abi}，\n  \
但当前 Python 是 ${PYTHON_VERSION} (${PYTHON_ABI})\n  \
请下载正确的 ABI 包: pip download pydantic_core --python-version ${PYTHON_MAJOR}.${PYTHON_MINOR} --platform manylinux2014_x86_64 --only-binary=:all: -d vendor_packages/${PYTHON_ABI}/"
            fi
            log_ok "ABI 校验通过: whl=${whl_abi} == python=${PYTHON_ABI}"
        fi
    fi

    # 阶段 1：批量安装（pip 会自动匹配 ABI）
    # conda 环境跳过 pydantic-core（由系统站点包提供）
    local install_pkgs="fastapi uvicorn pydantic starlette anyio tomli"
    if [ "${USE_SYSTEM_SITE_PACKAGES:-false}" != "true" ]; then
        install_pkgs="$install_pkgs pydantic-core"
    fi
    if pip install --no-index $LINKS_ARGS $install_pkgs 2>/dev/null; then
        log_ok "批量依赖安装成功"
    else
        # 阶段 2：逐个安装
        log_warn "批量安装部分失败，尝试逐个安装..."
        for dir in "${FIND_LINKS[@]}"; do
            for whl in "$dir"/*.whl; do
                [ -f "$whl" ] || continue
                local pkg_name=$(basename "$whl" | cut -d- -f1)
                if pip install --no-index --no-deps "$whl" 2>/dev/null; then
                    log_ok "$pkg_name"
                else
                    # 带依赖重试
                    pip install --no-index $LINKS_ARGS "$whl" 2>/dev/null && log_ok "$pkg_name" || log_error "$pkg_name 安装失败"
                fi
            done
        done
    fi

    # ---- 验证安装 ----
    step "6" "验证安装"

    local VERIFY_PKGS=("fastapi" "uvicorn" "pydantic" "starlette" "anyio" "pydantic_core" "tomli")
    local ALL_OK=true

    for pkg in "${VERIFY_PKGS[@]}"; do
        if python -c "import $pkg; print('   ✅ $pkg ' + getattr($pkg, '__version__', ''))" 2>/dev/null; then
            :
        else
            log_error "$pkg 导入失败"
            ALL_OK=false
        fi
    done

    if [ "$ALL_OK" = "false" ]; then
        die "依赖安装验证失败"
    fi
}

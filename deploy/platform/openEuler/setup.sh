#!/bin/bash
# ============================================================
# cross_env_manager · openEuler / IRAYPLEOS 专属 Python 安装
# ============================================================
#
# openEuler / IRAYPLEOS 通常自带 Python 3.9+，一般无需额外操作。
# 如果系统 Python 版本不足或缺失，尝试通过 dnf 安装。
#

log_info "openEuler/IRAYPLEOS 平台 Python 准备..."

# 尝试安装 venv 模块（部分镜像未默认安装）
if [ -n "${PYTHON3:-}" ] && [ -x "$PYTHON3" ]; then
    if ! $PYTHON3 -m venv --help &>/dev/null 2>&1; then
        log_info "安装 python3-venv..."
        dnf install -y python3-venv 2>/dev/null || log_warn "python3-venv 安装失败"
    fi
else
    # 系统完全没有 Python 3，尝试通过 dnf 安装
    log_warn "未检测到系统 Python 3，尝试 dnf 安装..."
    dnf install -y python3 python3-venv 2>/dev/null || \
        die "无法通过 dnf 安装 Python 3，请手动安装后重试"
fi

# openEuler 一般无需额外操作
log_ok "openEuler/IRAYPLEOS: Python 环境就绪"
return 0

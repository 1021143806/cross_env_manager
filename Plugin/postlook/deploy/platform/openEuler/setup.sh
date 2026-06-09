#!/bin/bash
# ============================================================
# postlook · openEuler 专属 Python 安装
# ============================================================
#
# openEuler 24.03 自带 Python 3.11.x，一般不需要额外操作。
# 如果系统 Python 版本不足，尝试通过 dnf 安装。
#

log_info "openEuler 平台 Python 准备..."

# 尝试安装 venv 模块（部分 openEuler 镜像未默认安装）
if ! $PYTHON3 -m venv --help &>/dev/null 2>&1; then
    log_info "安装 python3-venv..."
    dnf install -y python3-venv 2>/dev/null || log_warn "python3-venv 安装失败，将重试"
fi

# openEuler 一般无需额外操作，系统 Python 即可满足
log_ok "openEuler: Python 环境就绪"
return 0

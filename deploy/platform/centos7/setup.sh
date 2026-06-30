#!/bin/bash
# ============================================================
# cross_env_manager · CentOS 7 专属 Python 安装
# 安装策略（按优先级）:
#   1. 预编译包 python39_build.tar.gz 解压
#   2. 源码编译 Python-3.9.20.tar.xz
#
# 注：预编译包和源码包来自 postlook 共享的 rpms 目录
# ============================================================
#
# 成功后设置 PYTHON3 和 USE_SYSTEM_PYTHON=true

CENTOS7_PLATFORM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# rpms 目录与 postlook 共享（位于 Plugin/postlook/deploy/platform/centos7/rpms/）
SHARED_RPM_DIR="$PROJECT_DIR/Plugin/postlook/deploy/platform/centos7/rpms"

log_info "CentOS 7 Python 安装策略..."

# ---- 策略 1：预编译包 ----
PYTHON_TGZ="$SHARED_RPM_DIR/python39_build.tar.gz"
PYTHON_PREFIX="/usr/local/python3"

if [ -f "$PYTHON_TGZ" ]; then
    log_info "尝试预编译包安装..."

    # 清理旧版本
    rm -rf "$PYTHON_PREFIX" /usr/local/python39_build 2>/dev/null || true

    tar -xzf "$PYTHON_TGZ" -C /usr/local/

    # 兼容解压后目录名可能是 python39_build
    if [ -d /usr/local/python39_build ] && [ ! -d "$PYTHON_PREFIX" ]; then
        mv /usr/local/python39_build "$PYTHON_PREFIX"
    fi

    if [ -x "$PYTHON_PREFIX/bin/python3" ]; then
        # 验证 glibc 兼容性
        if $PYTHON_PREFIX/bin/python3 --version &>/dev/null; then
            PYTHON3="$PYTHON_PREFIX/bin/python3"
            USE_SYSTEM_PYTHON=true
            log_ok "预编译 Python 3.9 安装成功: $PYTHON3"
            return 0
        else
            log_warn "预编译包 glibc 不兼容 (目标 glibc: $(ldd --version 2>&1 | head -1))"
            rm -rf "$PYTHON_PREFIX" /usr/local/python39_build 2>/dev/null
        fi
    else
        log_warn "解压后未找到 $PYTHON_PREFIX/bin/python3"
        rm -rf "$PYTHON_PREFIX" /usr/local/python39_build 2>/dev/null
    fi
fi

# ---- 策略 2：源码编译 ----
PYTHON_SRC="$SHARED_RPM_DIR/Python-3.9.20.tar.xz"

if [ ! -f "$PYTHON_SRC" ]; then
    die "CentOS 7: 预编译包和源码包均不存在，无法安装 Python"
fi

log_info "开始源码编译 Python 3.9.20 (约 5-15 分钟)..."

# 检查编译依赖
command -v gcc &>/dev/null || die "缺少 gcc，无法编译 Python"
command -v make &>/dev/null || die "缺少 make，无法编译 Python"

# 从 rpms 安装 devel 包
for rpm_pkg in openssl-devel bzip2-devel libffi-devel; do
    if ! rpm -qa | grep -q "^${rpm_pkg}-"; then
        local rpm_file=$(ls "$SHARED_RPM_DIR/${rpm_pkg}"*.rpm 2>/dev/null | head -1)
        if [ -f "$rpm_file" ]; then
            log_info "安装 $rpm_pkg..."
            rpm -ivh "$rpm_file" --nodeps 2>/dev/null || true
        fi
    fi
done

log_info "解压源码..."
tar -xf "$PYTHON_SRC" -C /tmp/

cd /tmp/Python-3.9.20
log_info "配置..."
./configure --prefix="$PYTHON_PREFIX" --enable-optimizations --with-ensurepip=install 2>&1 | tail -1

log_info "编译中 (使用 $(nproc) 核)..."
make -j$(nproc) 2>&1 | tail -1

log_info "安装..."
make install 2>&1 | tail -1

cd /tmp
rm -rf /tmp/Python-3.9.20

if [ -x "$PYTHON_PREFIX/bin/python3" ]; then
    PYTHON3="$PYTHON_PREFIX/bin/python3"
    USE_SYSTEM_PYTHON=true
    log_ok "Python 3.9 源码编译安装成功: $PYTHON3"
else
    die "Python 源码编译失败"
fi

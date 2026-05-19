#!/bin/bash
# ============================================================
# postlook · 一键离线部署脚本
# 参考 deploy_iraypleos 模式，适配 FastAPI + Uvicorn
# ============================================================
set -e

# ---- 加载配置文件 ----
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF_FILE="$DEPLOY_DIR/deploy.conf"

if [ -f "$CONF_FILE" ]; then
    source "$CONF_FILE"
    echo "✅ 已加载部署配置: $CONF_FILE"
else
    echo "❌ 配置文件不存在: $CONF_FILE"
    exit 1
fi

# 项目根目录（deploy 的父目录）
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"
cd "$PROJECT_DIR"

echo "========================================"
echo "  $PROJECT_NAME · 离线部署"
echo "========================================"
echo "项目: $PROJECT_NAME"
echo "模块: $APP_MODULE"
echo "端口: $APP_PORT"
echo "用户: $(whoami)"
echo "时间: $(date)"
echo "========================================"

# ---- 内部函数：源码编译 Python 3.9 ----
_compile_python() {
    local SRC_DIR="$DEPLOY_DIR/centos7_rpms"
    local SRC_TAR="$SRC_DIR/Python-3.9.20.tar.xz"
    local PREFIX="/usr/local/python3"

    if [ ! -f "$SRC_TAR" ]; then
        echo "   ❌ 未找到 Python 源码包: $SRC_TAR"
        exit 1
    fi

    echo "   源码编译 Python 3.9 (约 5-15 分钟)..."
    echo "   检查编译依赖..."

    local MISSING=""
    command -v gcc &>/dev/null || MISSING="$MISSING gcc"
    command -v make &>/dev/null || MISSING="$MISSING make"
    if [ -n "$MISSING" ]; then
        echo "   ❌ 缺少编译依赖:$MISSING"
        echo "   请先安装: yum install -y gcc make openssl-devel bzip2-devel libffi-devel"
        exit 1
    fi

    echo "   解压源码..."
    tar -xf "$SRC_TAR" -C /tmp/

    cd /tmp/Python-3.9.20
    echo "   配置..."
    ./configure --prefix="$PREFIX" --enable-optimizations --with-ensurepip=install 2>&1 | tail -1
    echo "   编译中..."
    make -j$(nproc) 2>&1 | tail -1
    echo "   安装..."
    make install 2>&1 | tail -1

    cd "$PROJECT_DIR"
    rm -rf /tmp/Python-3.9.20

    if [ -x "$PREFIX/bin/python3" ]; then
        PYTHON3="$PREFIX/bin/python3"
        echo "   ✅ Python 3.9 编译安装成功: $PYTHON3"
    else
        echo "   ❌ 编译安装失败"
        exit 1
    fi
}

# ---- 1. 检查环境 ----
echo ""
echo "1. 检查环境..."

# 自动检测 python3 路径
if [ -n "$PYTHON3_PATH" ] && [ -x "$PYTHON3_PATH" ]; then
    PYTHON3="$PYTHON3_PATH"
elif command -v python3 &>/dev/null; then
    PYTHON3="python3"
elif [ -x "/opt/rh/rh-python39/root/bin/python3" ]; then
    PYTHON3="/opt/rh/rh-python39/root/bin/python3"
elif [ -x "/usr/local/bin/python3" ]; then
    PYTHON3="/usr/local/bin/python3"
else
    echo "   ❌ 未找到 python3"

    # 尝试从预编译包解压 Python 3.9
    SCL_RPM_DIR="$DEPLOY_DIR/centos7_rpms"
    PYTHON_TGZ="$SCL_RPM_DIR/python39_build.tar.gz"
    PYTHON_PREFIX="/usr/local/python3"

    if [ -f "$PYTHON_TGZ" ]; then
        echo "   检测到预编译 Python 3.9 包，解压安装..."
        tar -xzf "$PYTHON_TGZ" -C /usr/local/
        if [ -d /usr/local/python39_build ] && [ ! -d "$PYTHON_PREFIX" ]; then
            mv /usr/local/python39_build "$PYTHON_PREFIX"
        fi
        if [ -x "$PYTHON_PREFIX/bin/python3" ]; then
            # 验证 glibc 兼容性
            if $PYTHON_PREFIX/bin/python3 --version &>/dev/null; then
                PYTHON3="$PYTHON_PREFIX/bin/python3"
                echo "   ✅ Python 3.9 安装成功: $PYTHON3"
            else
                echo "   ⚠️  预编译包 glibc 不兼容，尝试源码编译..."
                rm -rf "$PYTHON_PREFIX" /usr/local/python39_build 2>/dev/null
                _compile_python
            fi
        else
            echo "   ❌ 解压后未找到 python3"
            exit 1
        fi
    elif [ -f "$SCL_RPM_DIR/Python-3.9.20.tar.xz" ]; then
        _compile_python
    else
        echo "   请安装 Python 3.9+:"
        echo "   在线安装: yum install -y centos-release-scl-rh && yum install -y rh-python39"
        echo "   离线安装: 将 python39_build.tar.gz 放入 $SCL_RPM_DIR/ 目录"
        echo "   或设置 PYTHON3_PATH 指向 python3 路径"
        exit 1
    fi
fi

echo "   Python: $($PYTHON3 --version 2>&1)"
echo "   Python路径: $PYTHON3"
echo "   项目目录: $PROJECT_DIR"
echo "   部署目录: $DEPLOY_DIR"

if [ ! -f "src/postlook/app.py" ]; then
    echo "   ❌ 未找到 src/postlook/app.py，请确保在项目根目录运行"
    exit 1
fi
echo "   ✅ 项目文件检查通过"

# ---- 2. 检查离线依赖包 ----
echo ""
echo "2. 检查离线依赖包..."
VENDOR_PATH="$PROJECT_DIR/$VENDOR_DIR"
if [ ! -d "$VENDOR_PATH" ]; then
    echo "   ❌ 离线包目录不存在: $VENDOR_PATH"
    echo "   提示: 请在联网环境执行以下命令下载依赖:"
    echo "   pip download fastapi uvicorn pydantic starlette anyio -d $VENDOR_DIR"
    exit 1
fi

WHL_COUNT=$(find "$VENDOR_PATH" -name "*.whl" | wc -l)
echo "   离线包数量: $WHL_COUNT"

# 检查关键包
KEY_PACKAGES=("fastapi" "uvicorn" "pydantic" "starlette" "anyio")
for pkg in "${KEY_PACKAGES[@]}"; do
    file=$(find "$VENDOR_PATH" -type f -iname "*${pkg}*.whl" | head -1)
    if [ -f "$file" ]; then
        echo "   ✅ $pkg: $(basename "$file")"
    else
        echo "   ❌ 缺少关键包: $pkg"
        exit 1
    fi
done

# ---- 3. 清理并创建虚拟环境 ----
echo ""
echo "3. 清理并创建虚拟环境..."
rm -rf "$VENV_DIR" 2>/dev/null || true
$PYTHON3 -m venv "$VENV_DIR"

if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "   ❌ 虚拟环境创建失败"
    exit 1
fi
echo "   ✅ 虚拟环境创建成功"

# ---- 4. 激活虚拟环境并安装依赖 ----
echo ""
echo "4. 激活虚拟环境..."
source "$VENV_DIR/bin/activate"
echo "   虚拟环境Python: $(python --version 2>&1)"

echo ""
echo "5. 安装离线依赖包..."
echo "   安装策略: 从本地 vendor_packages 离线安装"

if pip install --no-index --find-links="$VENDOR_PATH" fastapi uvicorn pydantic starlette anyio 2>/dev/null; then
    echo "   ✅ 批量依赖安装成功"
else
    echo "   ⚠️  批量安装失败，尝试逐个安装..."
    for whl in "$VENDOR_PATH"/*.whl; do
        pkg_name=$(basename "$whl")
        if pip install --no-index --no-deps "$whl" 2>/dev/null; then
            echo "   ✅ $pkg_name"
        else
            pip install --no-index "$whl" 2>/dev/null && echo "   ✅ $pkg_name" || echo "   ❌ $pkg_name 安装失败"
        fi
    done
fi

# ---- 6. 验证安装 ----
echo ""
echo "6. 验证安装..."

test_import() {
    if python -c "import $1; print('   ✅ $1')" 2>/dev/null; then
        return 0
    else
        echo "   ❌ $1 导入失败"
        return 1
    fi
}

test_import fastapi
test_import uvicorn
test_import pydantic
test_import starlette
test_import anyio

# ---- 7. 配置 Supervisor ----
echo ""
echo "7. 配置 Supervisor..."
SUPERVISOR_CONF="$SUPERVISOR_CONF_DIR/${PROJECT_NAME}.conf"
LOG_PATH="$LOG_DIR"

mkdir -p "$LOG_PATH" 2>/dev/null || true
# 确保日志目录属于 supervisor 运行用户
chown "$SUPERVISOR_USER:$SUPERVISOR_USER" "$LOG_PATH" 2>/dev/null || true

# 构建 uvicorn 启动命令（使用 venv 的 python，兼容 CentOS 7 SCL）
UVICORN_CMD="$PROJECT_DIR/$VENV_DIR/bin/python -m uvicorn $APP_MODULE --host $SERVER_HOST --port $APP_PORT"
if [ "$RELOAD_MODE" = "true" ]; then
    UVICORN_CMD="$UVICORN_CMD --reload"
fi

if [ -f "$SUPERVISOR_CONF" ]; then
    echo "   ⚠️  Supervisor配置文件已存在，将覆盖更新"
fi

cat > "$SUPERVISOR_CONF" << SUPERVISOR_EOF
[program:${PROJECT_NAME}]
command=$UVICORN_CMD
directory=$PROJECT_DIR
user=$SUPERVISOR_USER
autostart=true
autorestart=true
startsecs=10
startretries=3
redirect_stderr=true
stdout_logfile=$LOG_PATH/${PROJECT_NAME}.log
stdout_logfile_maxbytes=5MB
stdout_logfile_backups=0
stderr_logfile=$LOG_PATH/${PROJECT_NAME}_error.log
stderr_logfile_maxbytes=5MB
stderr_logfile_backups=0
environment=PYTHONPATH="$PROJECT_DIR"
SUPERVISOR_EOF

echo "   ✅ Supervisor配置文件已生成: $SUPERVISOR_CONF"

# ---- 8. 启动服务 ----
echo ""
echo "8. 启动服务..."

if command -v supervisorctl >/dev/null 2>&1; then
    supervisorctl reread 2>/dev/null || echo "   ⚠️  配置重读失败"
    supervisorctl update 2>/dev/null || echo "   ⚠️  配置更新失败"

    echo "   重启服务..."
    supervisorctl restart "$PROJECT_NAME" 2>/dev/null || {
        echo "   ⚠️  重启失败，尝试直接启动..."
        supervisorctl start "$PROJECT_NAME" 2>/dev/null
    }

    sleep "$START_WAIT"

    # 验证服务状态
    if supervisorctl status "$PROJECT_NAME" 2>/dev/null | grep -q "RUNNING"; then
        echo "   ✅ 服务已在 Supervisor 中运行"
    else
        echo "   ⚠️  服务未在 Supervisor 中运行，尝试直接启动..."
        nohup "$PROJECT_DIR/$VENV_DIR/bin/uvicorn" "$APP_MODULE" --host "$SERVER_HOST" --port "$APP_PORT" > "$LOG_PATH/${PROJECT_NAME}_direct.log" 2>&1 &
        sleep 2
        if pgrep -f "uvicorn.*$APP_MODULE" >/dev/null; then
            echo "   ✅ 已通过直接启动方式运行"
        else
            echo "   ❌ 服务启动失败"
        fi
    fi
else
    echo "   ⚠️  supervisorctl 未找到，直接启动..."
    nohup "$PROJECT_DIR/$VENV_DIR/bin/uvicorn" "$APP_MODULE" --host "$SERVER_HOST" --port "$APP_PORT" > "$LOG_PATH/${PROJECT_NAME}_direct.log" 2>&1 &
    sleep 2
    if pgrep -f "uvicorn.*$APP_MODULE" >/dev/null; then
        echo "   ✅ 服务已直接启动"
    else
        echo "   ❌ 服务启动失败"
    fi
fi

# ---- 9. 部署完成 ----
echo ""
echo "========================================"
echo "  $PROJECT_NAME 部署完成！"
echo "========================================"
echo ""
echo "部署信息:"
echo "  - 项目名称: $PROJECT_NAME"
echo "  - 应用模块: $APP_MODULE"
echo "  - 服务端口: $APP_PORT"
echo "  - 虚拟环境: $PROJECT_DIR/$VENV_DIR/"
echo "  - Supervisor配置: $SUPERVISOR_CONF"
echo "  - 离线包目录: $VENDOR_PATH"
echo ""
echo "访问地址:"
echo "  - 前端页面: http://localhost:$APP_PORT"
echo "  - API文档:  http://localhost:$APP_PORT/docs"
echo "  - 健康检查: http://localhost:$APP_PORT/api/health"
echo ""
echo "管理命令:"
echo "  - 查看状态: supervisorctl status $PROJECT_NAME"
echo "  - 重启服务: supervisorctl restart $PROJECT_NAME"
echo "  - 停止服务: supervisorctl stop $PROJECT_NAME"
echo "  - 查看日志: tail -f $LOG_PATH/${PROJECT_NAME}.log"
echo ""
echo "========================================"

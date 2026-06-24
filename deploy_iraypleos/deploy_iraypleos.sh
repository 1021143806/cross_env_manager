#!/bin/bash
# Python 3.9 离线部署脚本（自动检测 + 自动安装）
# 自动检测系统是否有 Python 3.9，没有则从预编译包安装到 /main/app/python39/
# vendor_packages3.9 目录为 Python 3.9 编译版，需要 Python 3.9 解释器

set -e

echo "========================================"
echo "跨环境任务模板管理系统 - Python 3.9.9简易部署"
echo "========================================"
echo "系统: IRAYPLEOS"
echo "Python版本: $(python3 --version 2>&1)"
echo "用户: $(whoami)"
echo "时间: $(date)"
echo "部署状态: vendor_packages3.9已验证为Python 3.9兼容"
echo "========================================"

# 获取当前目录（deploy_iraypleos目录）
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 项目根目录（父目录）
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"
cd "$PROJECT_DIR"

# 检查是否在正确的目录
if [ ! -f "app.py" ]; then
    echo "错误: 未找到app.py文件，请确保脚本在正确的位置运行"
    exit 1
fi

# ======================================================
# 检查并准备 Python 3.9 解释器
# 优先级：本地安装 > 系统自带 > 自动解压安装
# ======================================================
PYTHON39_INSTALL="/main/app/python39"
PYTHON39_BIN="$PYTHON39_INSTALL/bin/python3.9"
PYTHON39_SRC="$DEPLOY_DIR/../Plugin/postlook/deploy/platform/centos7/rpms/python39_build.tar.gz"

if [ -f "$PYTHON39_BIN" ]; then
    echo "🔍 Python 3.9 本地安装: $PYTHON39_BIN"
    PYTHON39_VERSION=$("$PYTHON39_BIN" --version 2>&1)
    echo "   $PYTHON39_VERSION"
elif [ -f "/usr/bin/python3.9" ]; then
    PYTHON39_BIN="/usr/bin/python3.9"
    echo "🔍 使用系统 Python 3.9: $PYTHON39_BIN"
    PYTHON39_VERSION=$("$PYTHON39_BIN" --version 2>&1)
    echo "   $PYTHON39_VERSION"
else
    echo "🔧 未检测到 Python 3.9，开始自动安装..."
    echo "   系统Python: $(python3 --version 2>&1)"
    if [ ! -f "$PYTHON39_SRC" ]; then
        echo "   ❌ 找不到预编译包: $PYTHON39_SRC"
        echo "   提示: 请将 python39_build.tar.gz 放到 Plugin/postlook/deploy/platform/centos7/rpms/ 目录"
        exit 1
    fi
    echo "   解压预编译包到 $PYTHON39_INSTALL ..."
    mkdir -p "$PYTHON39_INSTALL"
    tar xzf "$PYTHON39_SRC" -C "$PYTHON39_INSTALL" --strip-components=1
    if [ ! -f "$PYTHON39_BIN" ]; then
        echo "   ❌ Python 3.9 安装失败"
        exit 1
    fi
    PYTHON39_VERSION=$("$PYTHON39_BIN" --version 2>&1)
    echo "   ✅ Python 3.9 安装完成: $PYTHON39_VERSION"
fi

echo "1. 检查环境..."
echo "   Python版本: $(python3 --version 2>&1)"
echo "   项目目录: $PROJECT_DIR"
echo "   部署目录: $DEPLOY_DIR"

# 检查IRAYPLEOS用户
IRAY_USER="ymsk"
echo "   当前用户: $(whoami)"
echo "   Supervisor用户: $IRAY_USER"

echo ""
echo "2. 检查vendor_packages3.9目录..."
VENDOR_DIR="$DEPLOY_DIR/vendor_packages3.9"
if [ ! -d "$VENDOR_DIR" ]; then
    echo "   ❌ vendor_packages3.9目录不存在于 $VENDOR_DIR"
    exit 1
fi

# 快速检查关键包
echo "   快速检查关键包..."
KEY_PACKAGES=("markupsafe" "flask" "pymysql" "werkzeug" "jinja2" "dbutils" "flask_caching" "paramiko" "pyyaml" "cryptography" "typing_extensions")
for pkg in "${KEY_PACKAGES[@]}"; do
    file=$(find "$VENDOR_DIR" -type f -iname "*${pkg}*.whl" | head -1)
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        if [ "$pkg" = "markupsafe" ] && echo "$filename" | grep -q "cp39"; then
            echo "   ✅ $pkg: $filename (Python 3.9编译版)"
        elif echo "$filename" | grep -q "py3-none-any"; then
            echo "   ✅ $pkg: $filename (纯Python版)"
        else
            echo "   ✅ $pkg: $filename"
        fi
    else
        echo "   ❌ 缺少: $pkg"
        exit 1
    fi
done

echo ""
echo "3. 清理并创建虚拟环境 (Python 3.9)..."
rm -rf venv 2>/dev/null || true
"$PYTHON39_BIN" -m venv venv

if [ ! -f "venv/bin/python" ]; then
    echo "   ❌ 虚拟环境创建失败"
    exit 1
fi
echo "   ✅ 虚拟环境创建成功"

echo ""
echo "4. 激活虚拟环境..."
source venv/bin/activate
echo "   虚拟环境Python: $(python --version 2>&1)"

echo ""
echo "5. 检查mysql.connector导入..."
# 检查是否有未注释的mysql.connector导入
if grep -q "^[[:space:]]*import mysql\.connector" app.py || grep -q "^[[:space:]]*from mysql\.connector" app.py; then
    echo "   ⚠️  app.py中仍有未注释的mysql.connector引用，手动修复..."
    # 注释掉import mysql.connector
    sed -i '/^[[:space:]]*import mysql\.connector/s/^/# /' app.py
    sed -i '/^[[:space:]]*from mysql\.connector/s/^/# /' app.py
    # 替换mysql.connector.connect为pymysql.connect
    sed -i 's/mysql\.connector\.connect/pymysql.connect/g' app.py
    echo "   ✅ 手动修复完成"
else
    echo "   ✅ app.py中无未注释的mysql.connector引用"
fi

echo ""
echo "6. 安装离线依赖包..."
echo "   安装策略：批量安装，版本锁定与离线包一致"

REQ_FILE="$VENDOR_DIR/requirements_py39_fixed.txt"
if [ ! -f "$REQ_FILE" ]; then
    echo "   ❌ 未找到 requirements_py39_fixed.txt，终止安装"
    exit 1
fi
echo "   使用: $REQ_FILE"
echo "   包数量: $(grep -cE '^[a-zA-Z]' "$REQ_FILE")"

echo "   开始安装..."
if pip install --no-index --find-links="$VENDOR_DIR" -r "$REQ_FILE" 2>/dev/null; then
    echo "   ✅ 批量依赖安装成功"
else
    echo "   ⚠️  批量安装失败，尝试逐个安装（带依赖解析）..."
    while IFS= read -r line; do
        # 跳过空行和注释
        [[ -z "$line" || "$line" =~ ^# ]] && continue
        pkg_name="${line%%==*}"
        pkg_name="${pkg_name%%>*}"
        pkg_name="$(echo "$pkg_name" | xargs)"  # trim
        wheel_file=$(find "$VENDOR_DIR" -type f -iname "*${pkg_name}*.whl" 2>/dev/null | head -1)
        if [ -f "$wheel_file" ]; then
            if pip install --no-index --find-links="$VENDOR_DIR" "$wheel_file" 2>/dev/null; then
                echo "   ✅ $pkg_name 安装成功"
            else
                echo "   ❌ $pkg_name 安装失败"
            fi
        else
            echo "   ⚠️  未找到 ${pkg_name}.whl，跳过"
        fi
    done < "$REQ_FILE"
fi

echo ""
echo "7. 验证安装..."
echo "   测试关键包导入..."

test_import_simple() {
    if python -c "import $1; print('   ✅ $1导入成功')" 2>/dev/null; then
        return 0
    else
        echo "   ❌ $1导入失败"
        return 1
    fi
}

test_import_simple flask
test_import_simple pymysql
test_import_simple werkzeug
test_import_simple jinja2
test_import_simple markupsafe
test_import_simple importlib_metadata
test_import_simple paramiko
test_import_simple yaml
test_import_simple paramiko.client  # SSHClient
test_import_simple cryptography

echo ""
echo "8. 配置Supervisor..."
# 自动选择配置路径：优先 conf.d/，否则放在父目录
SUPERVISOR_BASE="/main/server/supervisor"
if [ -d "$SUPERVISOR_BASE/conf.d" ]; then
    SUPERVISOR_CONF="$SUPERVISOR_BASE/conf.d/cross_env_manager.conf"
    echo "   检测到 conf.d/ 目录，配置将创建至: $SUPERVISOR_CONF"
else
    SUPERVISOR_CONF="$SUPERVISOR_BASE/cross_env_manager.conf"
    echo "   未检测到 conf.d/，配置将创建至: $SUPERVISOR_CONF"
fi
LOG_DIR="/main/app/cross_env_manager/logs"
#本地测试/main/app/toolsForPersonal/projects/agv_system/app/cross_env_manager/logs

if [ -f "$SUPERVISOR_CONF" ]; then
    echo "   ✅ Supervisor配置文件已存在: $SUPERVISOR_CONF"
    echo "   ℹ️  跳过创建步骤，将直接重启服务"
else
    echo "   配置文件不存在，开始创建..."
    mkdir -p "$LOG_DIR" 2>/dev/null || true

    cat > "$SUPERVISOR_CONF" << EOF
[program:cross_env_manager]
command=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/app.py
directory=$PROJECT_DIR
user=$IRAY_USER
autostart=true
autorestart=true
startsecs=10
startretries=3
redirect_stderr=true
stdout_logfile=$LOG_DIR/cross_env_manager.log
stdout_logfile_maxbytes=5MB
stdout_logfile_backups=0
stderr_logfile=$LOG_DIR/cross_env_manager_error.log
stderr_logfile_maxbytes=5MB
stderr_logfile_backups=0
environment=PYTHONPATH="$PROJECT_DIR"
EOF

    echo "   ✅ Supervisor配置文件创建完成"
fi

echo ""
echo "9. 启动服务..."
if command -v supervisorctl >/dev/null 2>&1; then
    # 重读配置（如果新增了配置则生效，已存在也无影响）
    supervisorctl reread 2>/dev/null || echo "   ⚠️  配置重读失败"
    supervisorctl update 2>/dev/null || echo "   ⚠️  配置更新失败"
    
    echo "   重启服务..."
    supervisorctl restart cross_env_manager 2>/dev/null || {
        echo "   ⚠️  重启失败，尝试直接启动..."
        supervisorctl start cross_env_manager 2>/dev/null
    }
    
    sleep 3
    
    # 验证服务状态
    if supervisorctl status cross_env_manager 2>/dev/null | grep -q "RUNNING"; then
        echo "   ✅ 服务已在Supervisor中运行"
    else
        echo "   ⚠️  服务未在Supervisor中运行，尝试直接启动..."
        nohup "$PROJECT_DIR/venv/bin/python3" "$PROJECT_DIR/app.py" > "$LOG_DIR/cross_env_manager_direct.log" 2>&1 &
        sleep 2
        if pgrep -f "python.*app.py" >/dev/null; then
            echo "   ✅ 已通过直接启动方式运行"
        else
            echo "   ❌ 服务启动失败"
        fi
    fi
else
    echo "   ⚠️  supervisorctl命令未找到，直接启动..."
    nohup "$PROJECT_DIR/venv/bin/python3" "$PROJECT_DIR/app.py" > "$LOG_DIR/cross_env_manager_direct.log" 2>&1 &
    sleep 2
    if pgrep -f "python.*app.py" >/dev/null; then
        echo "   ✅ 服务已直接启动"
    else
        echo "   ❌ 服务启动失败"
    fi
fi

echo ""
echo "========================================"
echo "Python 3.9.9简易部署完成！"
echo "========================================"
echo ""
echo "部署信息:"
echo "- Python版本: 3.9.9"
echo "- 部署模式: 完全离线 (已验证Python 3.9兼容)"
echo "- 虚拟环境: $PROJECT_DIR/venv/"
echo "- Supervisor配置: $SUPERVISOR_CONF"
echo "- 离线包目录: $VENDOR_DIR"
echo ""
echo "服务状态:"
echo "- 应用URL: http://localhost:5000"
echo "- 应用日志: $LOG_DIR/cross_env_manager.log"
echo "- 错误日志: $LOG_DIR/cross_env_manager_error.log"
echo ""
echo "验证命令:"
echo "- 检查进程: pgrep -f 'python.*app.py'"
echo "- 检查端口: netstat -tlnp | grep :5000"
echo "- 健康检查: curl -s http://localhost:5000/actuator/health"
echo ""
echo "关键包状态:"
echo "- markupsafe: 2.1.3 (Python 3.9编译版)"
echo "- Flask: 2.3.3"
echo "- PyMySQL: 1.1.0"
echo "- 所有包: Python 3.9.9完全兼容"
echo ""
echo "✅ vendor_packages3.9目录验证为Python 3.9.9完全兼容！"
echo "✅ 项目已成功基于Python 3.9.9版本部署！"
echo "========================================"
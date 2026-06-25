#!/bin/bash
# ============================================================
# postlook · 一键更新 supervisor 配置 (HTTPS)
# 自动检测当前配置路径、追加 SSL 参数、重载 supervisor
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ---- 定位项目根目录 ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SSL_DIR="$PROJECT_ROOT/ssl"

# ---- 检查 SSL 证书 ----
if [ ! -f "$SSL_DIR/cert.pem" ] || [ ! -f "$SSL_DIR/key.pem" ]; then
    log_error "SSL 证书不存在: $SSL_DIR"
    echo "  期望文件: cert.pem, key.pem"
    echo "  请先执行: cd $PROJECT_ROOT && bash scripts/generate_ssl.sh"
    exit 1
fi
log_info "SSL 证书: $SSL_DIR"

# ---- 查找 supervisor 配置 ----
CONF_PATHS=(
    "/main/server/supervisor/postlook.conf"
    "/main/server/supervisor/conf.d/postlook.conf"
    "/main/app/supervisor/conf.d/postlook.conf"
)
CONF=""
for p in "${CONF_PATHS[@]}"; do
    if [ -f "$p" ]; then
        CONF="$p"
        break
    fi
done

if [ -z "$CONF" ]; then
    log_error "未找到 supervisor 配置，已尝试:"
    for p in "${CONF_PATHS[@]}"; do echo "  $p"; done
    exit 1
fi
log_info "找到配置: $CONF"

# ---- 检查是否已配 SSL ----
if grep -q -- '--ssl-keyfile' "$CONF"; then
    log_info "SSL 已配置，跳过"
    exit 0
fi

# ---- 备份 ----
BACKUP="${CONF}.bak.$(date +%Y%m%d_%H%M%S)"
cp "$CONF" "$BACKUP"
log_info "已备份: $BACKUP"

# ---- 更新 command 行 ----
SSL_PARAMS=" --ssl-keyfile $SSL_DIR/key.pem --ssl-certfile $SSL_DIR/cert.pem"

if grep -q -- '--port 5011' "$CONF"; then
    sed -i "s|--port 5011|--port 5011${SSL_PARAMS}|" "$CONF"
    log_info "已追加 SSL 参数到 command 行"
else
    sed -i "/^command=.*uvicorn.*5011/s|$|${SSL_PARAMS}|" "$CONF"
    log_info "已追加 SSL 参数到 command 行尾"
fi

# ---- 验证 ----
if ! grep -q -- '--ssl-keyfile' "$CONF"; then
    log_error "修改失败！已恢复备份"
    cp "$BACKUP" "$CONF"
    exit 1
fi

echo ""
echo "===== 新配置 ====="
grep '^command=' "$CONF"
echo "=================="
echo ""

# ---- 重载 supervisor ----
if command -v supervisorctl &>/dev/null; then
    log_info "重载 supervisor..."
    supervisorctl reread
    supervisorctl update
    supervisorctl restart postlook
    sleep 3
    log_info "验证..."
    echo -n "  HTTP:  "
    curl -s -m 2 http://127.0.0.1:5011/api/health 2>/dev/null || echo "拒绝 ✅"
    echo -n "  HTTPS: "
    curl -s -k -m 3 https://127.0.0.1:5011/api/health 2>/dev/null || echo "失败 ❌"
else
    log_warn "supervisorctl 不可用，请手动执行:"
    echo "  supervisorctl reread"
    echo "  supervisorctl update"
    echo "  supervisorctl restart postlook"
fi

echo ""
log_info "完成！已备份旧配置: $BACKUP"
echo "回滚命令: cp $BACKUP $CONF && supervisorctl reread && supervisorctl update && supervisorctl restart postlook"

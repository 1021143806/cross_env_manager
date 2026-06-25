#!/bin/bash
# ============================================================
# postlook · 一键更新 supervisor 配置 (HTTPS/HTTP 切换)
# 读取 deploy/deploy.conf 中的 USE_HTTPS 决定启用/禁用 SSL
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

# ---- 读取配置 ----
USE_HTTPS="false"
CONF_FILE="$PROJECT_ROOT/deploy/deploy.conf"
if [ -f "$CONF_FILE" ]; then
    source "$CONF_FILE" 2>/dev/null || true
    # USE_HTTPS 可能在 source 后还是默认值；用简单 grep 兜底
    if grep -q 'USE_HTTPS=false' "$CONF_FILE" 2>/dev/null; then
        USE_HTTPS="false"
    fi
fi
log_info "USE_HTTPS=$USE_HTTPS"

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
    log_error "未找到 supervisor 配置"
    exit 1
fi
log_info "找到配置: $CONF"

# ---- 备份 ----
BACKUP="${CONF}.bak.$(date +%Y%m%d_%H%M%S)"
cp "$CONF" "$BACKUP"
log_info "已备份: $BACKUP"

# ---- 根据 USE_HTTPS 更新 command 行 ----
SSL_PARAMS=" --ssl-keyfile $SSL_DIR/key.pem --ssl-certfile $SSL_DIR/cert.pem"
HAS_SSL=$(grep -q -- '--ssl-keyfile' "$CONF" && echo "true" || echo "false")
NEED_SSL="$USE_HTTPS"

if [ "$NEED_SSL" = "$HAS_SSL" ]; then
    log_info "配置已与 USE_HTTPS=$USE_HTTPS 一致，跳过"
    rm -f "$BACKUP"
    exit 0
fi

if [ "$NEED_SSL" = "true" ]; then
    if [ ! -f "$SSL_DIR/cert.pem" ] || [ ! -f "$SSL_DIR/key.pem" ]; then
        log_error "USE_HTTPS=true 但 SSL 证书不存在: $SSL_DIR"
        exit 1
    fi
    # 添加 SSL
    if grep -q -- '--port 5011' "$CONF"; then
        sed -i "s|--port 5011|--port 5011${SSL_PARAMS}|" "$CONF"
    else
        sed -i "/^command=.*uvicorn.*5011/s|$|${SSL_PARAMS}|" "$CONF"
    fi
    log_info "已添加 SSL 参数"
else
    # 移除 SSL
    sed -i 's| --ssl-keyfile [^ ]* --ssl-certfile [^ ]*||g' "$CONF"
    log_info "已移除 SSL 参数"
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
    if [ "$NEED_SSL" = "true" ]; then
        echo -n "  HTTP:  "
        curl -s -m 2 http://127.0.0.1:5011/api/health 2>/dev/null || echo "拒绝 ✅"
        echo -n "  HTTPS: "
        curl -s -k -m 3 https://127.0.0.1:5011/api/health 2>/dev/null || echo "失败 ❌"
    else
        echo -n "  HTTP:  "
        curl -s -m 3 http://127.0.0.1:5011/api/health 2>/dev/null || echo "失败 ❌"
    fi
else
    log_warn "supervisorctl 不可用，请手动重启: supervisorctl restart postlook"
fi

echo ""
log_info "完成！回滚: cp $BACKUP $CONF && supervisorctl reread && supervisorctl update && supervisorctl restart postlook"

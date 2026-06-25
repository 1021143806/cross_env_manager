#!/bin/bash
# ============================================================
# 生成 postlook 自签 SSL 证书 (10年有效)
# ============================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SSL_DIR="$PROJECT_ROOT/ssl"
mkdir -p "$SSL_DIR"

if [ -f "$SSL_DIR/cert.pem" ] && [ -f "$SSL_DIR/key.pem" ]; then
    echo "证书已存在: $SSL_DIR"
    openssl x509 -in "$SSL_DIR/cert.pem" -noout -dates -subject 2>/dev/null || true
    exit 0
fi

echo "生成自签证书..."
openssl req -x509 -newkey rsa:2048 \
    -keyout "$SSL_DIR/key.pem" \
    -out "$SSL_DIR/cert.pem" \
    -days 3650 -nodes \
    -subj "/CN=10.68.2.40" \
    -addext "subjectAltName=IP:10.68.2.40,IP:172.31.43.181,IP:127.0.0.1"

chmod 600 "$SSL_DIR/key.pem"
chmod 644 "$SSL_DIR/cert.pem"
echo "证书已生成: $SSL_DIR"
openssl x509 -in "$SSL_DIR/cert.pem" -noout -dates -subject

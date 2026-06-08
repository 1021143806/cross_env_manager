#!/bin/bash
# ============================================================
# postlook · Supervisor 配置与服务管理
# ============================================================

configure_supervisor() {
    step "7" "配置 Supervisor"

    # 校验关键变量非空
    if [ -z "${SUPERVISOR_CONF_DIR:-}" ] || [ -z "${PROJECT_NAME:-}" ]; then
        die "SUPERVISOR_CONF_DIR 或 PROJECT_NAME 未配置"
    fi

    SUPERVISOR_CONF="$SUPERVISOR_CONF_DIR/${PROJECT_NAME}.conf"
    LOG_PATH="$LOG_DIR"
    VENV_PATH="$PROJECT_DIR/${VENV_DIR:-venv}"

    # 确保日志目录存在
    mkdir -p "$LOG_PATH" 2>/dev/null || true
    chown "$SUPERVISOR_USER:$SUPERVISOR_USER" "$LOG_PATH" 2>/dev/null || true

    # 构建 uvicorn 启动命令
    UVICORN_CMD="$VENV_PATH/bin/python -m uvicorn $APP_MODULE --host $SERVER_HOST --port $APP_PORT"
    if [ "${RELOAD_MODE:-false}" = "true" ]; then
        UVICORN_CMD="$UVICORN_CMD --reload"
    fi

    # 备份已有配置（防止误覆盖其他服务）
    if [ -f "$SUPERVISOR_CONF" ]; then
        local BACKUP_FILE="$PROJECT_DIR/deploy/backup/${PROJECT_NAME}_$(date +%Y%m%d_%H%M%S).conf"
        mkdir -p "$(dirname "$BACKUP_FILE")" 2>/dev/null || true
        cp "$SUPERVISOR_CONF" "$BACKUP_FILE"
        log_warn "已备份旧 Supervisor 配置: $BACKUP_FILE"
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

    log_ok "Supervisor 配置已生成: $SUPERVISOR_CONF"
}

start_service() {
    step "8" "启动服务"

    VENV_PATH="$PROJECT_DIR/${VENV_DIR:-venv}"

    if [ "${SUPERVISOR_AVAILABLE:-false}" = "true" ]; then
        supervisorctl reread 2>/dev/null || log_warn "配置重读失败"
        supervisorctl update 2>/dev/null || log_warn "配置更新失败"

        log_info "重启服务..."
        supervisorctl restart "$PROJECT_NAME" 2>/dev/null || {
            log_warn "重启失败，尝试直接启动..."
            supervisorctl start "$PROJECT_NAME" 2>/dev/null
        }

        sleep "${START_WAIT:-3}"

        if supervisorctl status "$PROJECT_NAME" 2>/dev/null | grep -q "RUNNING"; then
            log_ok "服务已在 Supervisor 中运行"
        else
            log_warn "服务未通过 Supervisor 运行，尝试直接启动..."
            _direct_start
        fi
    else
        log_info "Supervisor 不可用，使用直接启动方式..."
        _direct_start
    fi
}

_direct_start() {
    local VENV_PATH="$PROJECT_DIR/${VENV_DIR:-venv}"
    local LOG_PATH="$LOG_DIR"

    nohup "$VENV_PATH/bin/uvicorn" "$APP_MODULE" \
        --host "$SERVER_HOST" \
        --port "$APP_PORT" \
        > "$LOG_PATH/${PROJECT_NAME}_direct.log" 2>&1 &

    sleep 2
    if pgrep -f "uvicorn.*$APP_MODULE" >/dev/null; then
        log_ok "已通过直接启动方式运行"
    else
        die "服务启动失败，请查看日志: $LOG_PATH/${PROJECT_NAME}_direct.log"
    fi
}

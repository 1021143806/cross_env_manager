#!/bin/bash
# ============================================================
# postlook · Supervisor 配置与服务管理
# ============================================================

# 确保 postlook 进程用户能读取 /var/log/messages 等系统日志
# 使用 sudo setfacl 添加读权限，避免改为 root 运行
ensure_syslog_access() {
    local run_user="$1"

    # 如果已经是 root，无需额外操作
    if [ "$run_user" = "root" ]; then
        return 0
    fi

    # 检查 sudo 是否可用
    if ! command -v sudo &>/dev/null; then
        log_warn "sudo 不可用，无法自动赋予系统日志读权限"
        log_warn "可手动执行: sudo setfacl -m u:$run_user:r /var/log/messages /var/log/secure /var/log/cron"
        return 0
    fi

    local syslog_files=()
    for f in /var/log/messages /var/log/secure /var/log/cron; do
        [ -f "$f" ] && syslog_files+=("$f")
    done

    if [ ${#syslog_files[@]} -eq 0 ]; then
        log_warn "未找到系统日志文件，跳过权限设置"
        return 0
    fi

    # 检查当前是否有读权限
    local need_fix=false
    for f in "${syslog_files[@]}"; do
        if ! sudo -u "$run_user" test -r "$f" 2>/dev/null; then
            need_fix=true
            break
        fi
    done

    if [ "$need_fix" = false ]; then
        log_info "运行用户 '$run_user' 已有系统日志读权限"
        return 0
    fi

    log_info "使用 sudo setfacl 为 '$run_user' 添加系统日志读权限..."

    # 先尝试加入 adm 组（部分系统 adm 组有读日志权限）
    if getent group adm &>/dev/null; then
        sudo usermod -aG adm "$run_user" 2>/dev/null && \
            log_ok "已添加 $run_user 到 adm 组"
    fi

    # 使用 setfacl 直接授予读权限（立即生效，不受 umask 影响）
    local fixed_count=0
    for f in "${syslog_files[@]}"; do
        if sudo setfacl -m u:"$run_user":r "$f" 2>/dev/null; then
            ((fixed_count++))
        fi
    done

    if [ "$fixed_count" -gt 0 ]; then
        log_ok "已为 $fixed_count 个系统日志文件添加 '$run_user' 读权限"
    fi

    # 验证
    local verify_ok=true
    for f in "${syslog_files[@]}"; do
        if ! sudo -u "$run_user" test -r "$f" 2>/dev/null; then
            log_warn "仍然无法读取: $f"
            verify_ok=false
        fi
    done

    if [ "$verify_ok" = true ]; then
        log_ok "系统日志读取权限验证通过"
    fi
}

configure_supervisor() {
    step "7" "配置 Supervisor"

    # 校验关键变量非空
    if [ -z "${SUPERVISOR_CONF_DIR:-}" ] || [ -z "${PROJECT_NAME:-}" ]; then
        die "SUPERVISOR_CONF_DIR 或 PROJECT_NAME 未配置"
    fi

    SUPERVISOR_CONF="$SUPERVISOR_CONF_DIR/${PROJECT_NAME}.conf"
    LOG_PATH="$LOG_DIR"
    VENV_PATH="$PROJECT_DIR/${VENV_DIR:-venv}"

    # 确保运行用户能读取系统日志
    ensure_syslog_access "$SUPERVISOR_USER"

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

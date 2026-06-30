#!/bin/bash
# ============================================================
# cross_env_manager · Supervisor 配置与服务管理
# Flask 项目适配版（不同于 postlook 的 uvicorn 启动方式）
# ============================================================

configure_supervisor() {
    step "7" "配置 Supervisor"

    # 校验关键变量非空
    if [ -z "${SUPERVISOR_CONF_DIR:-}" ] || [ -z "${PROJECT_NAME:-}" ]; then
        die "SUPERVISOR_CONF_DIR 或 PROJECT_NAME 未配置"
    fi

    SUPERVISOR_CONF="$SUPERVISOR_CONF_DIR/${PROJECT_NAME}.conf"
    LOG_PATH="$PROJECT_DIR/${LOG_DIR:-logs}"
    VENV_PATH="$PROJECT_DIR/${VENV_DIR:-venv}"

    # 自动选择配置路径：优先 conf.d/，否则放在父目录
    if [ -d "$SUPERVISOR_CONF_DIR/conf.d" ]; then
        SUPERVISOR_CONF="$SUPERVISOR_CONF_DIR/conf.d/${PROJECT_NAME}.conf"
        log_info "检测到 conf.d/ 目录，配置将创建至: $SUPERVISOR_CONF"
    fi

    log_info "Supervisor 配置路径: $SUPERVISOR_CONF"
    log_info "日志目录: $LOG_PATH"
    log_info "虚拟环境: $VENV_PATH"

    # 确保日志目录存在
    mkdir -p "$LOG_PATH" 2>/dev/null || true
    if [ -n "${SUPERVISOR_USER:-}" ]; then
        chown "$SUPERVISOR_USER:$SUPERVISOR_USER" "$LOG_PATH" 2>/dev/null || true
    fi

    # Flask 启动命令
    local FLASK_CMD="$VENV_PATH/bin/python $PROJECT_DIR/app.py"
    log_info "启动命令: $FLASK_CMD"

    # 备份已有配置
    if [ -f "$SUPERVISOR_CONF" ]; then
        local BACKUP_FILE="$DEPLOY_DIR/backup/${PROJECT_NAME}_$(date +%Y%m%d_%H%M%S).conf"
        mkdir -p "$(dirname "$BACKUP_FILE")" 2>/dev/null || true
        cp "$SUPERVISOR_CONF" "$BACKUP_FILE" || log_warn "备份配置失败（跳过）"
        log_warn "已备份旧 Supervisor 配置: $BACKUP_FILE"
    fi

    # 写入 Supervisor 配置
    cat > "$SUPERVISOR_CONF" << SUPERVISOR_EOF
[program:${PROJECT_NAME}]
command=$FLASK_CMD
directory=$PROJECT_DIR
user=${SUPERVISOR_USER:-ymsk}
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

    if [ ! -f "$SUPERVISOR_CONF" ]; then
        log_warn "Supervisor 配置文件不存在: $SUPERVISOR_CONF，跳过服务启动"
        return 0
    fi

    if [ "${SUPERVISOR_AVAILABLE:-false}" = "true" ]; then
        log_info "执行 supervisorctl reread..."
        supervisorctl reread 2>&1 | head -5 || log_warn "配置重读失败（非致命）"

        log_info "执行 supervisorctl update..."
        supervisorctl update 2>&1 | head -5 || log_warn "配置更新失败（非致命）"

        # 检查当前状态
        local sv_status
        sv_status=$(supervisorctl status "$PROJECT_NAME" 2>/dev/null)

        if echo "$sv_status" | grep -q "RUNNING"; then
            log_ok "服务已在 Supervisor 中运行"
            echo "$sv_status"
            return 0
        fi

        # 未运行则尝试 restart（已存在程序）或 start（新程序）
        if echo "$sv_status" | grep -q "STOPPED\|EXITED\|FATAL"; then
            log_info "重启服务: $PROJECT_NAME"
            supervisorctl restart "$PROJECT_NAME" 2>&1 || supervisorctl start "$PROJECT_NAME" 2>&1 || true
        else
            log_info "启动服务: $PROJECT_NAME"
            supervisorctl start "$PROJECT_NAME" 2>&1 || true
        fi

        # 等待启动
        local wait_sec="${START_WAIT:-3}"
        local retries=6
        log_info "等待服务启动（最长 $((wait_sec * retries)) 秒）..."
        for i in $(seq 1 "$retries"); do
            sleep "$wait_sec"
            sv_status=$(supervisorctl status "$PROJECT_NAME" 2>/dev/null)
            if echo "$sv_status" | grep -q "RUNNING"; then
                log_ok "服务已在 Supervisor 中运行"
                echo "$sv_status"
                return 0
            fi
            log_info "  状态检查 #${i}: $(echo "$sv_status" | awk '{print $2}')"
        done

        # 重试耗尽仍未 RUNNING
        log_warn "Supervisor 启动超时"
        log_warn "请手动排查: supervisorctl status $PROJECT_NAME"
        log_warn "查看日志: tail -50 ${LOG_PATH:-/main/log/app}/${PROJECT_NAME}.log"
        _direct_start
    else
        log_info "Supervisor 不可用，使用直接启动方式..."
        _direct_start
    fi
}

_direct_start() {
    local VENV_PATH="$PROJECT_DIR/${VENV_DIR:-venv}"
    local direct_log="$LOG_PATH/${PROJECT_NAME}_direct.log"

    mkdir -p "$LOG_PATH" 2>/dev/null || true

    log_info "直接启动: $VENV_PATH/bin/python $PROJECT_DIR/app.py"
    nohup "$VENV_PATH/bin/python" "$PROJECT_DIR/app.py" > "$direct_log" 2>&1 &

    sleep 2
    if pgrep -f "python.*app.py" >/dev/null; then
        log_ok "已通过直接启动方式运行"
    else
        log_warn "直接启动检查未通过，请查看日志: $direct_log"
    fi
}

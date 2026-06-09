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
        if groups "$run_user" 2>/dev/null | grep -qw "adm"; then
            log_info "用户 '$run_user' 已在 adm 组中，跳过"
        else
            sudo usermod -aG adm "$run_user" 2>/dev/null && \
                log_ok "已添加 $run_user 到 adm 组" || \
                log_warn "添加 $run_user 到 adm 组失败（非致命）"
        fi
    fi

    # 使用 setfacl 直接授予读权限（立即生效，不受 umask 影响）
    # 注意：bash set -e 下 ((count++)) 在 count=0 时会返回非零退出码，
    # 所以用 $((count+1)) 赋值方式规避
    local fixed_count=0
    for f in "${syslog_files[@]}"; do
        if sudo setfacl -m u:"$run_user":r "$f" 2>/dev/null; then
            fixed_count=$((fixed_count + 1))
            log_info "  setfacl OK: $f"
        else
            log_warn "  setfacl 失败: $f（可能已有权限）"
        fi
    done

    if [ "$fixed_count" -gt 0 ]; then
        log_ok "已为 $fixed_count 个系统日志文件添加 '$run_user' 读权限"
    else
        log_info "无需新增 setfacl 权限（可能已通过 group 授权）"
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

    log_info "Supervisor 配置路径: $SUPERVISOR_CONF"
    log_info "日志目录: $LOG_PATH"
    log_info "虚拟环境: $VENV_PATH"

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
    log_info "启动命令: $UVICORN_CMD"

    # 备份已有配置（防止误覆盖其他服务）
    if [ -f "$SUPERVISOR_CONF" ]; then
        local BACKUP_FILE="$PROJECT_DIR/deploy/backup/${PROJECT_NAME}_$(date +%Y%m%d_%H%M%S).conf"
        mkdir -p "$(dirname "$BACKUP_FILE")" 2>/dev/null || true
        cp "$SUPERVISOR_CONF" "$BACKUP_FILE"
        log_warn "已备份旧 Supervisor 配置: $BACKUP_FILE"
    fi

    # 写入 Supervisor 配置（检查目录是否可写）
    local conf_dir_ok=true
    if [ ! -d "$SUPERVISOR_CONF_DIR" ]; then
        log_warn "Supervisor 配置目录不存在: $SUPERVISOR_CONF_DIR，尝试创建..."
        mkdir -p "$SUPERVISOR_CONF_DIR" 2>/dev/null || conf_dir_ok=false
    fi
    if [ ! -w "$SUPERVISOR_CONF_DIR" ]; then
        log_warn "Supervisor 配置目录不可写: $SUPERVISOR_CONF_DIR（需要用 sudo 执行部署）"
        conf_dir_ok=false
    fi

    if [ "$conf_dir_ok" = "true" ]; then
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
    else
        log_warn "跳过写入 Supervisor 配置（目录不可写），提供配置内容如下:"
        log_warn "请手动执行: sudo tee $SUPERVISOR_CONF << 'EOF'"
        cat << SUPERVISOR_EOF
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
        log_warn "EOF"
        log_warn "然后执行: sudo supervisorctl reread && sudo supervisorctl update && sudo supervisorctl start $PROJECT_NAME"
    fi
}

start_service() {
    step "8" "启动服务"

    VENV_PATH="$PROJECT_DIR/${VENV_DIR:-venv}"

    if [ ! -f "$SUPERVISOR_CONF" ]; then
        log_warn "Supervisor 配置文件不存在: $SUPERVISOR_CONF，跳过服务启动"
        log_warn "请手动创建配置文件后执行: sudo supervisorctl reread && sudo supervisorctl update"
        return 0
    fi

    if [ "${SUPERVISOR_AVAILABLE:-false}" = "true" ]; then
        log_info "执行 supervisorctl reread..."
        supervisorctl reread 2>&1 | head -5 || log_warn "配置重读失败（非致命）"

        log_info "执行 supervisorctl update..."
        supervisorctl update 2>&1 | head -5 || log_warn "配置更新失败（非致命）"

        # update 后 supervisor 已自动启动程序，无需再 start
        # 检查当前状态
        local sv_status
        sv_status=$(supervisorctl status "$PROJECT_NAME" 2>/dev/null)

        if echo "$sv_status" | grep -q "RUNNING"; then
            log_ok "服务已在 Supervisor 中运行"
            echo "$sv_status"
            return 0
        fi

        # 未运行则尝试 start（首次部署时 reread+update 可能只是 added 而未启动）
        if echo "$sv_status" | grep -q "STOPPED\|EXITED\|FATAL"; then
            log_info "启动服务: $PROJECT_NAME"
            supervisorctl start "$PROJECT_NAME" 2>&1 || true
        fi

        # 等待启动，最多重试 6 次（每次 3s，共 18s）
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
        log_warn "Supervisor 启动超时，当前状态: $(echo "$sv_status" | awk '{print $2}')"
        log_warn "请手动排查: supervisorctl status $PROJECT_NAME"
        log_warn "查看日志: tail -50 ${LOG_PATH:-/main/log/app}/${PROJECT_NAME}.log"
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

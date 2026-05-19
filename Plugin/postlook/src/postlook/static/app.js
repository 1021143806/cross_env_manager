/**
 * postlook · 前端交互逻辑
 * 功能：主题切换、面板导航、日志查询、配置管理、服务状态检测
 */

document.addEventListener('DOMContentLoaded', () => {

    // ============================================================
    // 1. 主题切换
    // ============================================================
    const themeBtn = document.getElementById('themeBtn');
    const html = document.documentElement;

    // 从 localStorage 恢复主题，默认暗黑
    const savedTheme = localStorage.getItem('postlook-theme') || 'dark';
    html.setAttribute('data-theme', savedTheme);

    themeBtn.addEventListener('click', () => {
        const current = html.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', next);
        localStorage.setItem('postlook-theme', next);
    });

    // ============================================================
    // 2. 面板切换
    // ============================================================
    const navLinks = document.querySelectorAll('.sidebar nav a');
    const panels = document.querySelectorAll('.panel');

    function switchPanel(panelId) {
        // 更新导航激活状态
        navLinks.forEach(link => {
            link.classList.toggle('active', link.dataset.panel === panelId);
        });
        // 更新面板显示
        panels.forEach(panel => {
            panel.classList.toggle('active', panel.id === 'panel-' + panelId);
        });
        // 切换到服务状态面板时自动检测
        if (panelId === 'status') {
            checkServiceStatus();
        }
    }

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            switchPanel(link.dataset.panel);
        });
    });

    // ============================================================
    // 3. 日志查询
    // ============================================================
    const logForm = document.getElementById('logForm');
    const logResults = document.getElementById('logResults');

    logForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        // 构建请求体
        const formData = new FormData(logForm);
        const payload = {
            folder: formData.get('folder') || '',
            pattern: formData.get('pattern') || '*.log',
            keyword: formData.get('keyword') || null,
            line_start: parseInt(formData.get('line_start'), 10) || 1,
            line_end: parseInt(formData.get('line_end'), 10) || 100,
            tail: formData.get('tail') === 'true',
            recent_files: parseInt(formData.get('recent_files'), 10) || 10
        };

        // 移除空 keyword
        if (!payload.keyword) {
            delete payload.keyword;
        }

        // 显示加载状态
        logResults.innerHTML = '<div class="results-placeholder"><div class="spinner"></div><p>正在查询日志...</p></div>';

        try {
            const res = await fetch('/api/logs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || 'HTTP ' + res.status + ': ' + res.statusText);
            }

            const data = await res.json();
            renderLogResults(data);
        } catch (err) {
            logResults.innerHTML = '<div class="error-message">' +
                '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>' +
                '</svg><span>请求失败: ' + escapeHtml(err.message) + '</span></div>';
        }
    });

    /**
     * 渲染日志查询结果
     */
    function renderLogResults(data) {
        if (!data || !data.results || data.results.length === 0) {
            logResults.innerHTML = '<div class="results-placeholder">' +
                '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.3">' +
                '<circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/>' +
                '</svg><p>未找到匹配的日志内容</p></div>';
            return;
        }

        // 结果摘要
        var truncatedBadge = data.truncated
            ? '<span class="badge badge-truncated">结果已截断</span>'
            : '<span class="badge badge-complete">结果完整</span>';

        var html = '<div class="results-summary"><span>共找到 <strong>' + data.total_lines + '</strong> 条匹配行</span>' + truncatedBadge + '</div>';

        // 紧凑表格样式
        html += '<div class="log-table">';
        data.results.forEach(function(item) {
            var content = escapeHtml(item.content);
            var highlightedContent = data.keyword ? highlightKeyword(content, data.keyword) : content;

            html += '<div class="log-row">' +
                '<span class="log-row-line">' + item.line + '</span>' +
                '<span class="log-row-file">' + escapeHtml(item.file) + '</span>' +
                '<span class="log-row-content">' + highlightedContent + '</span>' +
                '</div>';
        });
        html += '</div>';

        logResults.innerHTML = html;
    }

    /**
     * HTML 转义，防止 XSS
     */
    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * 关键字高亮（不区分大小写）
     */
    function highlightKeyword(text, keyword) {
        if (!keyword) return text;
        var escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        var regex = new RegExp('(' + escaped + ')', 'gi');
        return text.replace(regex, '<span class="highlight">$1</span>');
    }

    // ============================================================
    // 4. 配置管理
    // ============================================================
    var configEditor = document.getElementById('configEditor');
    var loadConfigBtn = document.getElementById('loadConfigBtn');
    var saveConfigBtn = document.getElementById('saveConfigBtn');
    var configStatus = document.getElementById('configStatus');

    /**
     * 加载配置（预留接口 GET /api/config）
     */
    loadConfigBtn.addEventListener('click', async function() {
        configStatus.innerHTML = '<span class="info">正在加载配置...</span>';
        configStatus.className = 'config-status';

        try {
            var res = await fetch('/api/config');
            if (!res.ok) {
                throw new Error('HTTP ' + res.status + ': ' + res.statusText);
            }
            var data = await res.json();
            configEditor.value = data.content || data.config || JSON.stringify(data, null, 2);
            configStatus.innerHTML = '<span class="success">配置加载成功</span>';
            configStatus.className = 'config-status success';
        } catch (err) {
            configStatus.innerHTML = '<span class="info">配置接口暂未就绪 (' + escapeHtml(err.message) + ')，可直接编辑下方内容</span>';
            configStatus.className = 'config-status info';
        }
    });

    /**
     * 保存配置（预留接口 POST /api/config）
     */
    saveConfigBtn.addEventListener('click', async function() {
        var content = configEditor.value.trim();
        if (!content) {
            configStatus.innerHTML = '<span class="error">配置内容不能为空</span>';
            configStatus.className = 'config-status error';
            return;
        }

        configStatus.innerHTML = '<span class="info">正在保存配置...</span>';
        configStatus.className = 'config-status';

        try {
            var res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: content })
            });
            if (!res.ok) {
                var errData = await res.json().catch(function() { return {}; });
                throw new Error(errData.detail || 'HTTP ' + res.status);
            }
            configStatus.innerHTML = '<span class="success">配置保存成功</span>';
            configStatus.className = 'config-status success';
        } catch (err) {
            configStatus.innerHTML = '<span class="info">配置接口暂未就绪 (' + escapeHtml(err.message) + ')，配置内容仅在前端暂存</span>';
            configStatus.className = 'config-status info';
        }
    });

    // ============================================================
    // 5. 服务状态检测
    // ============================================================
    var statusInfo = document.getElementById('statusInfo');

    async function checkServiceStatus() {
        statusInfo.innerHTML = '<div class="status-loading"><div class="spinner"></div><p>正在检查服务状态...</p></div>';

        try {
            var res = await fetch('/api/health', { signal: AbortSignal.timeout(5000) });
            var healthData = await res.json().catch(function() { return null; });

            var isOnline = res.ok;
            var dotClass = isOnline ? 'online' : 'offline';
            var statusText = isOnline ? '在线' : '异常';

            var html = '<div class="status-grid">' +
                '<div class="status-item"><span class="status-label">服务状态</span>' +
                '<span class="status-value"><span class="status-indicator"><span class="status-dot ' + dotClass + '"></span>' + statusText + '</span></span></div>' +
                '<div class="status-item"><span class="status-label">服务端口</span><span class="status-value">5011</span></div>';

            if (healthData) {
                if (healthData.version) {
                    html += '<div class="status-item"><span class="status-label">版本</span><span class="status-value">' + escapeHtml(String(healthData.version)) + '</span></div>';
                }
            }

            html += '</div>';

            // 加载文件列表
            try {
                var filesRes = await fetch('/api/files');
                var filesData = await filesRes.json();
                if (filesData.directories && filesData.directories.length > 0) {
                    html += '<h3 style="margin-top: 24px; margin-bottom: 12px; font-size: 1rem; color: var(--text-secondary);">可查看的日志目录</h3>';
                    html += '<div class="file-browser">';

                    filesData.directories.forEach(function(dir) {
                        var dirClass = dir.exists ? '' : ' dir-missing';
                        html += '<div class="file-dir-card glass-card' + dirClass + '">';
                        html += '<div class="file-dir-header">';
                        html += '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>';
                        html += '<span class="dir-path">' + escapeHtml(dir.path) + '</span>';
                        html += '<span class="dir-count">' + (dir.file_count || 0) + ' 个文件</span>';
                        html += '</div>';

                        if (dir.exists && dir.files && dir.files.length > 0) {
                            html += '<div class="file-list">';
                            dir.files.forEach(function(file) {
                                var sizeStr = file.size > 1048576 ? (file.size / 1048576).toFixed(1) + ' MB' : (file.size > 1024 ? (file.size / 1024).toFixed(1) + ' KB' : file.size + ' B');
                                var timeStr = file.mtime_str || '';
                                html += '<div class="file-item" data-path="' + escapeHtml(file.path) + '" title="点击复制路径到日志查询">';
                                html += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
                                html += '<span class="file-name">' + escapeHtml(file.name) + '</span>';
                                html += '<span class="file-time">' + timeStr + '</span>';
                                html += '<span class="file-size">' + sizeStr + '</span>';
                                html += '</div>';
                            });
                            html += '</div>';
                        } else if (!dir.exists) {
                            html += '<div class="file-list"><p class="dir-empty">目录不存在</p></div>';
                        } else {
                            html += '<div class="file-list"><p class="dir-empty">目录为空</p></div>';
                        }
                        html += '</div>';
                    });

                    html += '</div>';
                }
            } catch (e) {
                // 文件列表加载失败不影响状态显示
            }

            statusInfo.innerHTML = html;

            // 点击文件项复制路径
            setTimeout(function() {
                document.querySelectorAll('.file-item').forEach(function(item) {
                    item.addEventListener('click', function() {
                        var path = this.getAttribute('data-path');
                        // 切换到日志查询面板并填入路径
                        document.querySelector('.sidebar nav a[data-panel="logs"]').click();
                        setTimeout(function() {
                            document.getElementById('folder').value = path;
                        }, 100);
                    });
                });
            }, 100);

        } catch (err) {
            statusInfo.innerHTML = '<div class="status-grid">' +
                '<div class="status-item"><span class="status-label">服务状态</span><span class="status-value"><span class="status-indicator"><span class="status-dot offline"></span>未连接</span></span></div>' +
                '<div class="status-item"><span class="status-label">服务端口</span><span class="status-value">5011</span></div>' +
                '<div class="status-item" style="grid-column: 1 / -1;"><span class="status-label">提示</span><span class="status-value" style="font-size: 0.85rem; color: var(--text-secondary);">后端服务尚未启动或 /api/health 接口未实现。启动 FastAPI 服务后状态将自动更新。</span></div>' +
                '</div>';
        }
    }

    /**
     * 格式化运行时间
     */
    function formatUptime(seconds) {
        if (seconds === undefined || seconds === null) return '未知';
        var d = Math.floor(seconds / 86400);
        var h = Math.floor((seconds % 86400) / 3600);
        var m = Math.floor((seconds % 3600) / 60);
        var s = Math.floor(seconds % 60);
        var parts = [];
        if (d > 0) parts.push(d + '天');
        if (h > 0) parts.push(h + '小时');
        if (m > 0) parts.push(m + '分钟');
        if (parts.length === 0 || s > 0) parts.push(s + '秒');
        return parts.join(' ');
    }
});

/**
 * postlook · 服务状态 (v0.15.0)
 * 统一侧栏布局
 */
(function () {
    var statusInfo, statusSidebar;
    var autoRefreshTimer = null;

    document.addEventListener('DOMContentLoaded', function () {
        statusInfo = document.getElementById('statusInfo');
        statusSidebar = document.getElementById('statusSidebar');
        checkServiceStatus();
        startAutoRefresh();
    });

    function startAutoRefresh() {
        if (autoRefreshTimer) clearInterval(autoRefreshTimer);
        autoRefreshTimer = setInterval(checkServiceStatus, 30000);
    }

    window.checkServiceStatus = function () {
        if (!statusInfo) return;
        statusInfo.innerHTML = '<div class="status-loading"><div class="spinner"></div><p>正在检查服务状态...</p></div>';

        fetch('/api/health').then(function (r) { return r.json(); }).then(function (healthData) {
            return Promise.all([
                Promise.resolve(healthData),
                fetch('/api/config').then(function (r) { return r.json(); }),
                fetch('/api/files').then(function (r) { return r.json(); }),
                fetch('/api/rules').then(function (r) { return r.json(); }),
                fetch('/api/logs/self?lines=5').then(function (r) { return r.json(); }),
            ]);
        }).then(function (results) {
            var health = results[0], config = results[1], files = results[2],
                rules = results[3], selfLogs = results[4];

            renderMainPanel(health, config, files, rules, selfLogs);
            renderSidebar(files);
        }).catch(function () {
            statusInfo.innerHTML = '<div style="padding:24px"><div style="color:var(--danger);font-weight:600;font-size:0.9rem">⚠ 服务不可达</div><p style="color:var(--text-tertiary);font-size:0.78rem;margin-top:8px">无法连接后端 API，请检查服务是否运行中。</p></div>';
            if (statusSidebar) statusSidebar.innerHTML = '<div style="font-size:0.72rem;color:var(--text-tertiary);padding:4px">—</div>';
        });
    };

    function renderMainPanel(health, config, files, rules, selfLogs) {
        var html = '<div style="padding:20px 24px">';

        // ── 服务概览 ──
        html += '<div class="status-section"><h4>系统概览</h4>';
        html += '<div class="status-grid">';
        html += '<div class="stat-item"><span class="stat-label">状态</span><span class="stat-value" style="color:#34d399">● 运行中</span></div>';
        html += '<div class="stat-item"><span class="stat-label">版本</span><span class="stat-value">v' + (health.version || '—') + '</span></div>';
        html += '<div class="stat-item"><span class="stat-label">白名单目录</span><span class="stat-value">' + (config.root_dirs || []).length + ' 个</span></div>';
        html += '<div class="stat-item"><span class="stat-label">最大行数</span><span class="stat-value">' + (config.max_lines || 100) + '</span></div>';
        html += '<div class="stat-item"><span class="stat-label">规则数量</span><span class="stat-value">' + (rules.count || rules.rules ? rules.rules.length : 0) + '</span></div>';
        html += '<div class="stat-item"><span class="stat-label">下载上限</span><span class="stat-value">' + (config.max_download_size_mb || 200) + ' MB</span></div>';
        html += '</div></div>';

        // ── 白名单目录详情 ──
        html += '<div class="status-section"><h4>白名单目录</h4>';
        if (config.root_dirs) {
            config.root_dirs.forEach(function (dir) {
                var found = files.directories ? files.directories.find(function (d) { return d.path === dir; }) : null;
                var exists = found && found.exists;
                var icon = exists ? '<span style="color:#34d399">●</span>' : '<span style="color:#ef4444">●</span>';
                var fileCount = found ? ' (' + found.file_count + ' 文件)' : '';
                html += '<div class="dir-row">' + icon + ' <code>' + escapeHtml(dir) + '</code>' + fileCount + '</div>';
            });
        }
        html += '</div>';

        // ── 最新日志文件 ──
        html += '<div class="status-section"><h4>最新日志文件</h4>';
        var allFiles = [];
        if (files.directories) {
            files.directories.forEach(function (d) {
                if (d.files) d.files.forEach(function (f) {
                    allFiles.push({ path: d.path + '/' + f.name, mtime: f.mtime, name: f.name, size: f.size });
                });
            });
        }
        allFiles.sort(function (a, b) { return b.mtime - a.mtime; });
        html += '<div style="max-height:200px;overflow-y:auto">';
        for (var i = 0; i < Math.min(allFiles.length, 15); i++) {
            var f = allFiles[i];
            var dt = new Date(f.mtime * 1000);
            html += '<div class="dir-row" style="cursor:pointer" onclick="navigateToLogs(\'' + f.path.replace(/'/g, "\\'") + '\')">' +
                '<span style="color:var(--text-tertiary);font-size:0.7rem;width:130px;flex-shrink:0">' + dt.toLocaleString() + '</span>' +
                '<code style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + escapeHtml(f.name) + '</code>' +
                '<span style="color:var(--text-tertiary);font-size:0.7rem">' + formatBytes(f.size) + '</span>' +
                '</div>';
        }
        html += '</div></div>';

        // ── postlook 自身日志 ──
        html += '<div class="status-section"><h4>postlook 自身日志（最新5行）</h4>';
        if (selfLogs && selfLogs.results) {
            selfLogs.results.forEach(function (r) {
                html += '<div style="font-size:0.7rem;color:var(--text-secondary);padding:2px 0;font-family:monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + escapeHtml(r.content) + '</div>';
            });
        } else {
            html += '<div style="color:var(--text-tertiary);font-size:0.72rem">暂无</div>';
        }
        html += '</div>';

        html += '</div>';
        statusInfo.innerHTML = html;
    }

    function renderSidebar(files) {
        if (!statusSidebar) return;
        if (!files || !files.directories) {
            statusSidebar.innerHTML = '<div style="font-size:0.72rem;color:var(--text-tertiary);padding:4px">暂无数据</div>';
            return;
        }
        var html = '<div class="sb-labels">';
        files.directories.forEach(function (d) {
            var exists = d.exists;
            var dotColor = exists ? '#34d399' : '#ef4444';
            var label = d.path.split('/').pop() || d.path;
            html += '<label class="sb-label" style="opacity:' + (exists ? '1' : '0.55') + '">' +
                '<span class="sb-legend-dot" style="background:' + dotColor + '"></span> ' +
                escapeHtml(label) +
                '<span class="count">' + (d.file_count || 0) + '</span></label>';
        });
        html += '</div>';
        statusSidebar.innerHTML = html;
    }
})();

function navigateToLogs(path) {
    location.href = 'logs.html?folder=' + encodeURIComponent(path);
}

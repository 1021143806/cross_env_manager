/**
 * postlook · 服务状态页面逻辑
 */
document.addEventListener('DOMContentLoaded', function() {
    var statusInfo = document.getElementById('statusInfo');

    checkServiceStatus();

    function checkServiceStatus() {
        statusInfo.innerHTML = '<div class="status-loading"><div class="spinner"></div><p>正在检查服务状态...</p></div>';

        // 健康检查
        fetch('/api/health').then(function(r){return r.json();}).then(function(healthData){
            // 并行加载文件和配置
            return Promise.all([
                Promise.resolve(healthData),
                fetch('/api/config').then(function(r){return r.json();}),
                fetch('/api/files').then(function(r){return r.json();}),
                fetch('/api/rules').then(function(r){return r.json();}),
                fetch('/api/logs/self?lines=5').then(function(r){return r.json();}),
            ]);
        }).then(function(results){
            var health = results[0];
            var config = results[1];
            var files = results[2];
            var rules = results[3];
            var selfLogs = results[4];

            var html = '<div style="padding:20px 24px">';

            // 服务概览
            html += '<div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">';
            html += '<div style="width:10px;height:10px;border-radius:50%;background:#34d399;box-shadow:0 0 8px rgba(52,211,153,0.5)"></div>';
            html += '<span style="font-weight:600;font-size:1rem">服务运行中</span>';
            html += '<span style="color:var(--text-tertiary);font-size:0.82rem">v' + (health.version || '—') + '</span>';
            html += '</div>';

            // 配置摘要
            html += '<div class="status-section"><h4>配置</h4>';
            html += '<div class="status-grid">';
            html += '<div class="stat-item"><span class="stat-label">白名单目录</span><span class="stat-value">' + (config.root_dirs || []).length + ' 个</span></div>';
            html += '<div class="stat-item"><span class="stat-label">最大行数</span><span class="stat-value">' + (config.max_lines || 100) + '</span></div>';
            html += '<div class="stat-item"><span class="stat-label">规则数量</span><span class="stat-value">' + (rules.count || 0) + '</span></div>';
            html += '<div class="stat-item"><span class="stat-label">下载上限</span><span class="stat-value">' + (config.max_download_size_mb || 200) + ' MB</span></div>';
            html += '</div></div>';

            // 白名单目录
            html += '<div class="status-section"><h4>白名单目录</h4>';
            if (config.root_dirs) {
                config.root_dirs.forEach(function(dir) {
                    var found = files.directories ? files.directories.find(function(d) { return d.path === dir; }) : null;
                    var exists = found && found.exists;
                    var icon = exists ? '<span style="color:#34d399">●</span>' : '<span style="color:#ef4444">●</span>';
                    var fileCount = found ? ' (' + found.file_count + ' 文件)' : '';
                    html += '<div class="dir-row">' + icon + ' <code>' + dir + '</code>' + fileCount + '</div>';
                });
            }
            html += '</div>';

            // 最新文件
            html += '<div class="status-section"><h4>最新日志文件</h4>';
            var allFiles = [];
            if (files.directories) {
                files.directories.forEach(function(d) {
                    if (d.files) d.files.forEach(function(f) {
                        allFiles.push({path: d.path + '/' + f.name, mtime: f.mtime, name: f.name, size: f.size});
                    });
                });
            }
            allFiles.sort(function(a,b){return b.mtime - a.mtime;});
            html += '<div style="max-height:200px;overflow-y:auto">';
            for (var i=0;i<Math.min(allFiles.length,15);i++) {
                var f = allFiles[i];
                var dt = new Date(f.mtime * 1000);
                html += '<div class="dir-row" style="cursor:pointer" onclick="location=\'logs.html?folder=' + encodeURIComponent(f.path) + '\'">' +
                    '<span style="color:var(--text-tertiary);font-size:0.72rem;width:130px;flex-shrink:0">' + dt.toLocaleString() + '</span>' +
                    '<code style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + f.name + '</code>' +
                    '<span style="color:var(--text-tertiary);font-size:0.72rem">' + formatBytes(f.size) + '</span>' +
                    '</div>';
            }
            html += '</div></div>';

            // 自检日志
            html += '<div class="status-section"><h4>postlook 自身日志（最新5行）</h4>';
            if (selfLogs && selfLogs.results) {
                selfLogs.results.forEach(function(r) {
                    html += '<div style="font-size:0.72rem;color:var(--text-secondary);padding:2px 0;font-family:monospace">' + escapeHtml(r.content) + '</div>';
                });
            }
            html += '</div>';

            html += '</div>';
            statusInfo.innerHTML = html;

            // 侧栏文件树
            renderFileTree(files);
        }).catch(function(){
            statusInfo.innerHTML = '<div style="padding:20px"><div style="color:var(--danger);font-weight:600">服务不可达</div><p style="color:var(--text-tertiary);font-size:0.82rem">无法连接后端 API，请检查服务是否运行中。</p></div>';
        });
    }

    function renderFileTree(data) {
        var sidebar = document.getElementById('statusSidebar');
        if (!sidebar) return;
        if (!data || !data.directories) {
            sidebar.innerHTML = '<div style="font-size:0.75rem;color:var(--text-tertiary);padding:4px">暂无数据</div>';
            return;
        }
        var html = '';
        data.directories.forEach(function(d) {
            if (!d.exists) {
                html += '<div style="color:var(--text-tertiary);font-size:0.72rem;padding:2px 0;opacity:0.5">✗ ' + d.path + '</div>';
                return;
            }
            html += '<div style="margin-bottom:4px">';
            html += '<div class="sb-dir" style="font-size:0.75rem;font-weight:600;padding:4px 0;color:var(--text-secondary)">' + d.path + '</div>';
            var showFiles = d.files ? d.files.slice(0, 8) : [];
            showFiles.forEach(function(f) {
                var dt = new Date(f.mtime * 1000);
                html += '<div class="sb-file-item" title="' + f.path + '" style="cursor:pointer" onclick="navigateToLogs(\'' + f.path.replace(/'/g,"\\'") + '\')">' +
                    '<span class="sb-file-name">' + f.name + '</span>' +
                    '<span class="sb-file-size">' + formatBytes(f.size) + '</span>' +
                    '</div>';
            });
            if (d.files && d.files.length > 8) {
                html += '<div style="font-size:0.7rem;color:var(--text-tertiary);padding:2px 0">… 还有 ' + (d.files.length - 8) + ' 个文件</div>';
            }
            html += '</div>';
        });
        sidebar.innerHTML = html;
    }

    // 自动刷新（每30秒）
    setInterval(checkServiceStatus, 30000);
});

function navigateToLogs(path) {
    location.href = 'logs.html?folder=' + encodeURIComponent(path);
}

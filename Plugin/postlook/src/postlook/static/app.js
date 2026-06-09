/**
 * postlook · 前端交互逻辑
 * 功能：主题切换、面板导航、日志查询、配置管理、服务状态检测、拓扑图
 */

document.addEventListener('DOMContentLoaded', () => {
    console.log('postlook v3 loaded, navLinks:', document.querySelectorAll('.topbar-tab').length, 'panels:', document.querySelectorAll('.panel').length);

    // ============================================================
    // 0. 拓扑数据（必须在 switchPanel 之前定义）
    // ============================================================
    var cy = null;
    var topoInited = false;

    // 拓扑数据：优先从 API 加载，失败时用内置兜底
    var TOPO_DATA = null;
    var TOPO_LOADING = false;

    // 规则缓存（预编译的着色/注解规则）
    var _compiledRules = [];

    function buildTopoData(categories, services) {
        var cats = {};
        categories.forEach(function(c) { cats[c.id] = c; });
        var nodes = [{data:{id:'server',label:'postlook\n'+window.location.hostname,type:'server',weight:100},classes:'server'}];
        var edges = [];
        for (var k in cats) {
            var c = cats[k];
            nodes.push({data:{id:c.id,label:c.label,type:'category',cat:k,weight:60},classes:'category '+k});
            edges.push({data:{source:'server',target:c.id}});
        }
        for (var i=0;i<services.length;i++) {
            var s = services[i];
            var sz = Math.max(20, Math.min(50, (s.size_mb || 0.1) * 0.35 + 18));
            nodes.push({data:{id:s.id,label:s.name||s.id,type:'service',cat:s.category,desc:s.desc||'',logDir:s.log_dir||'',logFile:s.log_file||'',sizeMB:s.size_mb||0,weight:sz},classes:'service '+s.category});
            if (cats[s.category]) edges.push({data:{source:cats[s.category].id,target:s.id}});
        }
        return {nodes:nodes,edges:edges,services:services,categories:cats};
    }

    function loadTopoData(callback) {
        if (TOPO_DATA) return callback(TOPO_DATA);
        if (TOPO_LOADING) { setTimeout(function(){ loadTopoData(callback); }, 200); return; }
        TOPO_LOADING = true;
        fetch('/api/topology-config').then(function(r){return r.json();}).then(function(data){
            TOPO_DATA = buildTopoData(data.categories || [], data.services || []);
            callback(TOPO_DATA);
        }).catch(function(){
            // 兜底数据
            var cats = [
                {id:'apps',label:'应用系统',color:'#0abde3'},
                {id:'planner',label:'路径规划',color:'#f87171'},
                {id:'middleware',label:'中间件',color:'#fbbf24'},
                {id:'system',label:'系统日志',color:'#4ade80'},
                {id:'database',label:'数据库',color:'#a855f7'}
            ];
            var svcs = [
                {id:'gateway',name:'Gateway',category:'apps',log_dir:'/main/app/gateway/logs',log_file:'GATEWAY.log',size_mb:48},
                {id:'bms',name:'BMS',category:'apps',log_dir:'/main/app/bms/logs',log_file:'BMS.log',size_mb:96},
                {id:'nacos',name:'Nacos',category:'middleware',log_dir:'/main/server/nacos/logs',log_file:'nacos.log',size_mb:14},
                {id:'messages',name:'messages',category:'system',log_dir:'/var/log',log_file:'messages',size_mb:4},
                {id:'mariadb',name:'MariaDB',category:'database',log_dir:'/main/server/mysql',log_file:'slow-sql',size_mb:1}
            ];
            TOPO_DATA = buildTopoData(cats, svcs);
            callback(TOPO_DATA);
        });
    }

    function calcRadialLayout(topoData) {
        var pos = {};
        var cats = Object.keys(topoData.categories);
        for (var i = 0; i < cats.length; i++) {
            var cat = topoData.categories[cats[i]];
            var a = (2 * Math.PI * i) / cats.length - Math.PI / 2;
            var cx = Math.cos(a) * 260, cy = Math.sin(a) * 260;
            pos[cat.id] = { x: cx, y: cy };
            var svcs = topoData.services.filter(function(s) { return s.category === cats[i]; });
            var svcLen = svcs.length;
            var arc = Math.min(3.5, Math.max(0.4, svcLen * 0.13));
            var dist = 110 + Math.max(0, svcLen - 8) * 8;
            for (var j = 0; j < svcLen; j++) {
                var sa = svcLen <= 1 ? a : a - arc / 2 + (arc * j / (svcLen - 1));
                pos[svcs[j].id] = { x: cx + Math.cos(sa) * dist, y: cy + Math.sin(sa) * dist };
            }
        }
        pos['server'] = { x: 0, y: 0 };
        return pos;
    }

    // ============================================================
    // 1. 主题切换
    // ============================================================
    const themeBtn = document.getElementById('themeBtn');
    const html = document.documentElement;

    const savedTheme = localStorage.getItem('postlook-theme') || 'dark';
    html.setAttribute('data-theme', savedTheme);

    themeBtn.addEventListener('click', () => {
        const current = html.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', next);
        localStorage.setItem('postlook-theme', next);
        if (typeof cy !== 'undefined' && cy) updateTopoTheme(next);
    });

    // ============================================================
    // 2. 面板切换（顶部导航栏）
    // ============================================================
    const navLinks = document.querySelectorAll('.topbar-tab');
    const panels = document.querySelectorAll('.panel');
    const sidePanels = document.querySelectorAll('.sidebar-panel');

    function switchPanel(panelId) {
        navLinks.forEach(link => {
            link.classList.toggle('active', link.dataset.panel === panelId);
        });
        panels.forEach(panel => {
            panel.classList.toggle('active', panel.id === 'panel-' + panelId);
        });
        // 切换左侧子功能栏
        sidePanels.forEach(sp => {
            sp.classList.toggle('active', sp.id === 'sidebar-' + panelId);
        });
        // 记住当前 tab
        localStorage.setItem('postlook-panel', panelId);
        if (panelId === 'status') {
            checkServiceStatus();
        }
        if (panelId === 'topology') {
            document.querySelector('.content').style.padding = '0';
            document.querySelector('.content').style.overflow = 'hidden';
            initTopology();
        } else {
            document.querySelector('.content').style.padding = '';
            document.querySelector('.content').style.overflow = '';
        }
    }

    // 恢复上次的 tab
    var savedPanel = localStorage.getItem('postlook-panel') || 'logs';
    switchPanel(savedPanel);

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            if (link.dataset.panel) {
                e.preventDefault();
                switchPanel(link.dataset.panel);
            }
        });
    });

    // ============================================================
    // 3. 日志查询
    // ============================================================
    const logForm = document.getElementById('logForm');
    const logResults = document.getElementById('logResults');
    var queryTimer = null;
    var queryLoading = false;

    logForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        // 防抖：300ms 内重复提交忽略
        if (queryLoading) return;
        queryLoading = true;
        clearTimeout(queryTimer);
        queryTimer = setTimeout(function() { queryLoading = false; }, 2000);

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
            queryLoading = false;
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
            // ① 先按搜索关键字高亮
            var rendered = data.keyword ? highlightKeyword(content, data.keyword) : content;
            // ② 再按规则着色 + 注解
            rendered = applyRulesAndAnnotations(rendered, item.file);

            html += '<div class="log-row">' +
                '<span class="log-row-line">' + item.line + '</span>' +
                '<span class="log-row-file">' + escapeHtml(item.file) + '</span>' +
                '<span class="log-row-content">' + rendered + '</span>' +
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

    /**
     * 对日志行应用规则着色 + 注解
     * @param {string} content - 已 escapeHtml 的日志内容
     * @param {string} file - 文件名（用于 file 过滤）
     * @returns {string} 渲染后的 HTML
     */
    function applyRulesAndAnnotations(content, file) {
        if (!_compiledRules || _compiledRules.length === 0) return content;

        var annotations = [];
        var matched = false;

        _compiledRules.forEach(function(rule) {
            // file 过滤：如果规则指定了 file，当前行文件名必须匹配
            if (rule.filePattern && file && !rule.filePattern.test(file)) return;

            var matchInfo = null;
            if (rule.type === 'hex') {
                // 归一化：去空格、转小写
                var normalizedContent = content.replace(/\s/g, '').toLowerCase();
                var normalizedMatch = rule.normalizedHex;
                if (normalizedContent.indexOf(normalizedMatch) !== -1) {
                    matchInfo = { index: normalizedContent.indexOf(normalizedMatch), length: normalizedMatch.length };
                }
            } else if (rule.type === 'regex') {
                var m = rule.compiledRegex.exec(content);
                if (m) {
                    matchInfo = { index: m.index, length: m[0].length };
                }
            } else if (rule.type === 'keyword') {
                if (rule.compiledRegex.test(content)) {
                    var k = content.match(rule.compiledRegex);
                    if (k) {
                        matchInfo = { index: k.index, length: k[0].length };
                    }
                }
            }

            if (matchInfo) {
                // 着色：包裹 16px 宽的色条到整行前面
                var style = 'color:' + (rule.color || 'inherit') + ';' +
                    (rule.background ? 'background:' + rule.background + ';' : '') +
                    (rule.bold ? 'font-weight:700;' : '');
                content = '<span style="border-left:3px solid ' + (rule.color || 'transparent') + ';padding-left:6px;' + style + '">' +
                    content + '</span>';

                // 注解：添加 annotation 徽标
                if (rule.annotation) {
                    annotations.push(
                        '<span class="rule-annotation" style="background:' + (rule.color || '#818cf8') + '20;color:' +
                        (rule.color || '#818cf8') + ';border:1px solid ' + (rule.color || '#818cf8') + '40">' +
                        rule.annotation + '</span>'
                    );
                }
                matched = true;
            }
        });

        // 有注解时拼在内容前方
        if (annotations.length > 0) {
            content = annotations.join(' ') + ' ' + content;
        }

        return content;
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

    // ---- 日志目录扫描 ----
    var scanBtn = document.getElementById('scanBtn');
    var scanBase = document.getElementById('scanBase');
    var scanResults = document.getElementById('scanResults');
    var scanTimer = null;

    scanBtn.addEventListener('click', function() {
        doScan();
    });

    // 回车触发扫描
    scanBase.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            doScan();
        }
    });

    function doScan() {
        var base = scanBase.value.trim();
        if (!base) return;

        scanBtn.disabled = true;
        scanBtn.textContent = '扫描中...';
        scanResults.innerHTML = '<div class="scan-loading"><div class="spinner"></div><span>正在扫描 ' + escapeHtml(base) + ' ...</span></div>';

        fetch('/api/scan-dirs?base=' + encodeURIComponent(base))
            .then(function(res) { return res.json(); })
            .then(function(data) {
                scanBtn.disabled = false;
                scanBtn.textContent = '扫描';

                if (!data.exists) {
                    scanResults.innerHTML = '<p class="scan-empty">路径不存在: ' + escapeHtml(base) + '</p>';
                    return;
                }
                if (!data.dirs || data.dirs.length === 0) {
                    scanResults.innerHTML = '<p class="scan-empty">未找到 log/logs 目录</p>';
                    return;
                }

                var html = '<div class="scan-dir-list">';
                data.dirs.forEach(function(dir) {
                    var mtimeStr = dir.latest_mtime ? new Date(dir.latest_mtime * 1000).toLocaleString('zh-CN') : '-';
                    html += '<label class="scan-dir-item">';
                    html += '<input type="checkbox" class="scan-check" value="' + escapeHtml(dir.path) + '" checked>';
                    html += '<span class="scan-dir-path">' + escapeHtml(dir.path) + '</span>';
                    html += '<span class="scan-dir-info">' + dir.file_count + ' 文件 · ' + mtimeStr + '</span>';
                    html += '</label>';
                });
                html += '<button id="addToWhitelistBtn" class="btn-primary" style="margin-top: 10px;">添加到白名单</button>';
                html += '</div>';
                scanResults.innerHTML = html;

                // 添加到白名单按钮
                document.getElementById('addToWhitelistBtn').addEventListener('click', function() {
                    var checked = document.querySelectorAll('.scan-check:checked');
                    var paths = [];
                    checked.forEach(function(cb) { paths.push(cb.value); });
                    if (paths.length === 0) return;

                    // 读取当前 textarea 内容，追加到 root_dirs
                    var content = configEditor.value;
                    // 匹配 root_dirs 行
                    var newDirs = paths.map(function(p) { return '"' + p + '"'; }).join(', ');
                    if (content.indexOf('root_dirs = [') !== -1) {
                        // 在现有数组中追加
                        content = content.replace(/root_dirs = \[([^\]]*)\]/, function(match, existing) {
                            var trimmed = existing.trim();
                            var suffix = trimmed ? ', ' + newDirs : newDirs;
                            return 'root_dirs = [' + trimmed + suffix + ']';
                        });
                    }
                    configEditor.value = content;
                    configStatus.innerHTML = '<span class="success">已添加 ' + paths.length + ' 个目录到白名单，请点击"保存配置"生效</span>';
                    configStatus.className = 'config-status success';
                });
            })
            .catch(function(err) {
                scanBtn.disabled = false;
                scanBtn.textContent = '扫描';
                scanResults.innerHTML = '<p class="scan-empty">扫描失败: ' + escapeHtml(err.message) + '</p>';
            });
    }

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
                        document.querySelector('.topbar-tab[data-panel="logs"]').click();
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

    // ============================================================
    // 8. 拓扑图
    // ============================================================
    function initTopology() {
        if (topoInited) { if (cy) { cy.resize(); cy.fit(undefined, 30); } return; }
        topoInited = true;

        var container = document.getElementById('cy');
        if (!container) return;

        var statusEl = document.getElementById('topoStatus');
        if (statusEl) statusEl.textContent = '加载配置中...';

        loadTopoData(function(data) {
            if (!data || !data.nodes) return;
            _initTopoWithData(container, data);
        });
    }

    function _initTopoWithData(container, data) {
        cy = cytoscape({
        container: container,
            elements: { nodes: data.nodes, edges: data.edges },
            style: [
                { selector: '.server', style: { 'shape':'ellipse','background-color':'#818cf8','background-opacity':0.2,'label':'data(label)','color':'#e0e0f0','font-size':'13px','font-weight':'bold','text-valign':'center','text-halign':'center','width':110,'height':110,'border-width':2,'border-color':'#818cf8','text-wrap':'wrap','text-max-width':'80px' } },
                { selector: '.category', style: { 'shape':'ellipse','label':'data(label)','color':'#c0c0e0','font-size':'12px','font-weight':'bold','text-valign':'center','text-halign':'center','width':75,'height':75,'border-width':2,'border-color':'#a0a0c0' } },
                { selector: '.apps', style: { 'background-color':'#0abde3','background-opacity':0.18,'border-color':'#0abde3' } },
                { selector: '.planner', style: { 'background-color':'#f87171','background-opacity':0.18,'border-color':'#f87171' } },
                { selector: '.middleware', style: { 'background-color':'#fbbf24','background-opacity':0.18,'border-color':'#fbbf24' } },
                { selector: '.system', style: { 'background-color':'#4ade80','background-opacity':0.18,'border-color':'#4ade80' } },
                { selector: '.database', style: { 'background-color':'#a855f7','background-opacity':0.18,'border-color':'#a855f7' } },
                { selector: '.service', style: { 'shape':'ellipse','label':'data(label)','color':'#e8e0f0','font-size':'10px','text-valign':'center','text-halign':'center','width':'data(weight)','height':'data(weight)','border-width':2 } },
                { selector: '.service:selected', style: { 'border-width':3,'border-color':'#fff' } },
                { selector: 'edge', style: { 'width':1.2,'line-color':'rgba(129,140,248,0.35)','curve-style':'bezier','opacity':0.7,'line-dash-pattern':[4,8],'line-dash-offset':0 } }
            ],
            layout: { name:'preset', positions: calcRadialLayout(data), animate:true, animationDuration:800 },
            wheelSensitivity: 0.3, userZoomingEnabled: true, userPanningEnabled: true, minZoom: 0.15, maxZoom: 3,
            autoungrabify: false, autounselectify: false,
            ready: function() {
            document.getElementById('topoStatus').textContent = (data.services.length + 5) + ' 节点 · 滚轮缩放';
            setTimeout(function(){ cy.resize(); cy.fit(undefined, 40); }, 150);

            // 节点动态悬浮
            var floatPhases = {}, floatTime = 0, basePos = {};
            cy.nodes().forEach(function(n) { basePos[n.id()] = { x: n.position('x'), y: n.position('y') }; floatPhases[n.id()] = Math.random() * Math.PI * 2; });

            // 拖拽松手回弹
            cy.on('free', '.service', function(evt) {
                var n = evt.target, id = n.id();
                if (basePos[id]) { n.animate({ position: basePos[id] }, { duration: 300 }); }
            });

            // 每40ms微调位置
            setInterval(function() {
                floatTime += 0.05;
                cy.nodes().forEach(function(n) {
                    var id = n.id(), o = basePos[id];
                    if (!o || n.grabbed()) return;
                    floatPhases[id] += 0.03;
                    var p = floatPhases[id];
                    var dx = Math.sin(p * 0.7 + floatTime) * 12 + Math.cos(p * 1.3) * 10;
                    var dy = Math.cos(p * 0.9 + floatTime) * 12 + Math.sin(p * 1.1) * 10;
                    n.position({ x: o.x + dx, y: o.y + dy });
                    n.style('width', n.data('weight') * (1 + Math.sin(p) * 0.04));
                    n.style('height', n.data('weight') * (1 + Math.sin(p) * 0.04));
                });
            }, 40);

        }
        });

        // 节点点击事件（在 ready 回调之外注册，确保不被错过）
        cy.on('tap', '.service', function(evt) { showTopoDetail(evt.target); });
        cy.on('tap', function(evt) { if(evt.target===cy) closeTopoDetail(); });

        // 左侧图层
        var layersDiv = document.getElementById('topoLayers');
        if (layersDiv) {
            var html = '<div class="sb-labels">';
            for (var k in data.categories) {
                var c = data.categories[k];
                var count = data.services.filter(function(s){return s.category===k;}).length;
                html += '<label class="sb-label"><input type="checkbox" checked data-cat="'+k+'" onchange="toggleLayer(\''+k+'\',this.checked)"> <span class="sb-legend-dot" style="background:'+c.color+'"></span> '+c.label+' <span class="count">'+count+'</span></label>';
            }
            html += '</div>';
            layersDiv.innerHTML = html;
        }
        // 左侧图例
        var legendDiv = document.querySelector('.sb-legend');
        if (legendDiv) {
            var html = '';
            for (var k in data.categories) {
                var c = data.categories[k];
                html += '<div class="sb-legend-item"><span class="sb-legend-dot" style="background:'+c.color+'"></span>'+c.label+'</div>';
            }
            legendDiv.innerHTML = html;
        }
    }

    window.toggleLayer = function(cat, show) {
        if (!cy) return;
        var sel = show ? '.' + cat : '.' + cat;
        if (show) { cy.nodes('.' + cat).style('display','element'); cy.nodes('.category.'+cat).style('display','element'); }
        else { cy.nodes('.' + cat).style('display','none'); }
    };

    window.filterTopoNodes = function(query) {
        if (!cy) return;
        var q = query.toLowerCase();
        cy.nodes('.service').forEach(function(n) {
            var label = (n.data('label')||'').toLowerCase();
            var desc = (n.data('desc')||'').toLowerCase();
            n.style('display', (q === '' || label.indexOf(q) >= 0 || desc.indexOf(q) >= 0) ? 'element' : 'none');
        });
    };

    function showTopoDetail(node) {
        try {
            var el = document.getElementById('topoDetail');
            var name = document.getElementById('topoDetailName');
            var body = document.getElementById('topoDetailBody');
            if (!el || !name || !body) { console.warn('topoDetail DOM missing'); return; }
            el.style.display = 'flex';
            var label = node.data('label'), logDir = node.data('logDir'), logFile = node.data('logFile'), desc = node.data('desc')||'', sizeMB = node.data('sizeMB')||0;
            name.textContent = label + (desc ? ' — ' + desc : '');
            var html = '<div style="margin-bottom:8px;color:var(--text-tertiary);font-size:0.75rem">路径: '+(logDir||'—')+' | 主日志: '+(logFile||'—')+' | '+(sizeMB?sizeMB.toFixed(1)+' MB':'')+'</div>';
            html += '<div style="margin-bottom:4px;font-weight:600;font-size:0.8rem">日志文件</div>';
            html += '<div id="topoFileList" style="margin-bottom:10px">加载中...</div>';
            html += '<div style="font-weight:600;font-size:0.8rem">最新预览</div>';
            html += '<div class="log-preview" id="topoLogPreview">加载中...</div>';
            html += '<div style="margin-top:10px;display:flex;gap:6px">';
            if (logFile) html += '<button class="file-actions" style=\"padding:4px 12px\" onclick=\"window.open(\'/api/download?path='+encodeURIComponent((logDir||'')+'/'+logFile)+'\')\">⬇ 下载</button>';
            html += '<button class="file-actions" style=\"padding:4px 12px\" onclick=\"closeTopoDetail()\">关闭</button></div>';
            body.innerHTML = html;

            // 加载文件列表
            fetch('/api/files').then(function(r){return r.json();}).then(function(data){
                var fl = document.getElementById('topoFileList');
                if (!fl) return;
                var items = '';
                if (data.directories && logDir) {
                    for (var i=0;i<data.directories.length;i++){
                        var d=data.directories[i];
                        if (d.path===logDir||d.path.indexOf(logDir+'/')===0){
                            for (var j=0;j<Math.min(d.files.length,10);j++){
                                var f=d.files[j], sz=f.size<1024?f.size+'B':f.size<1048576?(f.size/1024).toFixed(1)+'KB':(f.size/1048576).toFixed(1)+'MB';
                                items += '<div class="file-row"><span class="file-name" title="'+f.path+'">'+f.name+'</span><span class="file-size">'+sz+'</span><div class="file-actions"><button onclick="window.open(\'/api/download?path='+encodeURIComponent(f.path)+'\')">⬇</button><button onclick="viewTopoLog(\''+encodeURIComponent(f.path)+'\')">👁</button></div></div>';
                            }
                            break;
                        }
                    }
                }
                fl.innerHTML = items || '暂无文件';
            }).catch(function(){ var fl=document.getElementById('topoFileList'); if(fl)fl.innerHTML='加载失败'; });

            // 加载日志预览
            if (logFile && logDir) {
                fetch('/api/logs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({folder:logDir,pattern:logFile,tail:true,line_start:1,line_end:60,recent_files:1})})
                    .then(function(r){return r.json();}).then(function(data){
                        var lp = document.getElementById('topoLogPreview');
                        if (!lp) return;
                        var lines = '';
                        if (data.results) for (var i=0;i<data.results.length;i++){ var c=data.results[i].content,cls=/ERROR|error|Error/.test(c)?'error':/WARN|warn/.test(c)?'warn':''; lines += '<div class="log-line '+cls+'" style="font-size:0.68rem;white-space:nowrap;line-height:1.3">'+escapeHtml(c)+'</div>'; }
                        lp.innerHTML = lines || '暂无日志';
                    }).catch(function(){ var lp=document.getElementById('topoLogPreview'); if(lp)lp.innerHTML='加载失败'; });
            }
        } catch(e) {
            console.error('showTopoDetail error:', e);
        }
    }

    window.closeTopoDetail = function() { document.getElementById('topoDetail').style.display = 'none'; };
    window.viewTopoLog = function(path) {
        document.querySelector('.topbar-tab[data-panel="logs"]').click();
        setTimeout(function(){ document.getElementById('folder').value = decodeURIComponent(path); }, 150);
    };

    function updateTopoTheme(theme) {
        if (!cy) return;
        var serverText = theme === 'dark' ? '#e0e0f0' : '#2a2a4e';
        var serverBorder = theme === 'dark' ? '#818cf8' : '#6366f1';
        cy.style().selector('.server').style('color', serverText).style('border-color', serverBorder).update();
        cy.style().selector('.category').style('color', theme==='dark'?'#c0c0e0':'#3a3a5a').update();
        cy.style().selector('.service').style('color', theme==='dark'?'#e8e0f0':'#4a4a6a').update();
    }

    // ============================================================
    // 9. 规则加载（侧栏按钮 + 着色/注解缓存）
    // ============================================================
    function compileRule(rule) {
        var compiled = {};
        // 复制标量字段
        compiled.type = rule.type || 'keyword';
        compiled.color = rule.color || null;
        compiled.background = rule.background || null;
        compiled.bold = rule.bold || false;
        compiled.annotation = rule.annotation || null;
        compiled.folder = rule.folder || null;
        compiled.pattern = rule.pattern || null;
        compiled.match = rule.match || '';
        compiled.name = rule.name || '';

        // 编译 file 过滤器
        if (rule.file) {
            compiled.filePattern = new RegExp(rule.file.replace(/\*/g, '.*').replace(/\?/g, '.'), 'i');
        } else {
            compiled.filePattern = null;
        }

        // 按 type 编译匹配模式
        if (compiled.type === 'hex') {
            // 16 进制：去空格，转小写，存归一化字符串
            compiled.normalizedHex = rule.match.replace(/\s+/g, '').toLowerCase();
        } else if (compiled.type === 'regex') {
            compiled.compiledRegex = new RegExp(rule.match, 'gi');
        } else {
            // keyword：按 | 分隔，编译正则
            compiled.compiledRegex = new RegExp('(' + rule.match.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
        }
        return compiled;
    }

    function loadRules() {
        fetch('/api/rules').then(function(r){return r.json();}).then(function(data){
            var container = document.getElementById('rulesContainer');
            if (!container) return;
            var rules = data.rules || [];

            // 预编译所有规则（着色/注解）
            _compiledRules = [];
            rules.forEach(function(rule) {
                _compiledRules.push(compileRule(rule));
            });

            // 过滤出有 folder 的快捷查询规则，渲染侧栏按钮
            var queryRules = rules.filter(function(r){ return r.folder; });
            if (queryRules.length === 0) {
                container.innerHTML = '<div style="font-size:0.75rem;color:var(--text-tertiary);padding:4px">无规则</div>';
                return;
            }
            var html = '';
            queryRules.forEach(function(rule, idx) {
                // 用原始 rules 索引引用
                var origIdx = rules.indexOf(rule);
                html += '<button class="sb-btn rule-btn" title="'+(rule.desc||'')+'" data-rule-idx="'+origIdx+'">'+(rule.name||'?')+'</button>';
            });
            container.innerHTML = html;
            // 委托事件处理
            container.querySelectorAll('.rule-btn').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    var idx = parseInt(this.getAttribute('data-rule-idx'));
                    var rule = rules[idx];
                    if (!rule) return;
                    var form = document.getElementById('logForm');
                    if (rule.folder) document.getElementById('folder').value = rule.folder;
                    if (rule.pattern) document.getElementById('pattern').value = rule.pattern;
                    // 规则匹配关键词作为默认关键字
                    if (rule.match) document.getElementById('keyword').value = rule.match;
                    if (rule.line_start) document.getElementById('line_start').value = rule.line_start;
                    if (rule.line_end) document.getElementById('line_end').value = rule.line_end;
                    document.querySelector('.topbar-tab[data-panel="logs"]').click();
                    setTimeout(function() { 
                        form.dispatchEvent(new Event('submit', {cancelable: true, bubbles: true}));
                    }, 150);
                });
            });
        }).catch(function(){
            var c = document.getElementById('rulesContainer');
            if (c) c.innerHTML = '<div style="font-size:0.75rem;color:var(--text-tertiary);padding:4px">规则加载失败</div>';
        });
    }
    loadRules();
});

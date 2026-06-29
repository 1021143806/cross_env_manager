/**
 * postlook · 日志查询 v2.1
 * 架构分层: State → DOM → Init → Events → API → Render → Feedback → Live → Utils
 */
(function() {

    // ════════════════════════════════════════════════════════════
    //  [State] 模块状态
    // ════════════════════════════════════════════════════════════

    var _queryLoading = false;
    var _liveActive = false;
    var _isLiveQuery = false;
    var _liveKeyword = null;
    var _liveInterval = 3000;  // 当前轮询间隔 ms
    var _liveCountdown = 60;   // 自动关闭倒计时 s
    var _liveTimer = null, _liveCountdownId = null;
    var _debounceTimer = null;
    var _seenLines = {};       // { filename: { lineNumber: true } }
    var _lastShellCmd = '';
    var _justQueried = false;  // 查询刚触发，跳过 history 下拉

    var _dateQueries = [];
    var _editingFilename = null;

    var STORAGE_KEY = 'postlook-search-history-v2';
    var MAX_HISTORY = 15;
    var LIVE_INTERVAL_MIN = 3000;
    var LIVE_INTERVAL_MAX = 30000;
    var LIVE_TIMEOUT = 60;

    // ════════════════════════════════════════════════════════════
    //  [DOM] DOM 引用缓存
    // ════════════════════════════════════════════════════════════

    var els = {};

    function cacheEls() {
        ['folder','pattern','keyword','lineCount','tail','recentFiles',
         'chipFilters','btnQuery','btnLive','btnLiveLabel','queryTime',
         'logResults','historyDropdown','dateQueriesContainer',
         'shellCmdBar','shellCmdText','feedbackMsg'].forEach(function(id) {
            els[id] = document.getElementById(id);
        });
    }

    // ════════════════════════════════════════════════════════════
    //  [Init] 统一初始化入口
    // ════════════════════════════════════════════════════════════

    function init() {
        cacheEls();

        // 0. URL 参数自动填入（来自拓扑跳转）
        try {
            var params = new URLSearchParams(window.location.search);
            var urlFolder = params.get('folder');
            if (urlFolder) {
                var folderEl = document.getElementById('folder');
                if (folderEl) {
                    folderEl.value = decodeURIComponent(urlFolder);
                    // 自动触发查询
                    setTimeout(function() { doQuery(); }, 300);
                }
            }
        } catch (e) {}

        // 1. 规则引擎（着色 + 自定义注释）
        if (typeof loadRules === 'function') {
            loadRules();
        }

        // 2. 快捷查询列表
        loadDateQueries();

        // 3. 页面事件绑定
        bindSidebarEvents();
        bindFormEvents();
        bindFolderEvents();
        bindButtonEvents();

        // 4. 加载版本号
        fetch('/api/help').then(function(r) { return r.json(); }).then(function(d) {
            var el = document.getElementById('postlookVersion');
            if (el && d.version) el.textContent = 'v' + d.version;
        }).catch(function() {});
    }

    document.addEventListener('DOMContentLoaded', init);

    // ════════════════════════════════════════════════════════════
    //  [Events] 事件绑定
    // ════════════════════════════════════════════════════════════

    function bindSidebarEvents() {
        if (!els.dateQueriesContainer) return;
        els.dateQueriesContainer.addEventListener('click', function(e) {
            var delBtn = e.target.closest('.dq-delete');
            if (delBtn) {
                e.stopPropagation();
                deleteDateQuery(parseInt(delBtn.getAttribute('data-idx')));
                return;
            }
            var item = e.target.closest('.dq-item');
            if (!item) return;
            var q = _dateQueries[parseInt(item.getAttribute('data-idx'))];
            if (!q) return;
            applyDateQuery(q);
        });
    }

    function bindFormEvents() {
        els.pattern.addEventListener('change', function() { autoQuery(); });
        els.lineCount.addEventListener('change', function() { autoQuery(); });
        els.tail.addEventListener('change', function() { autoQuery(); });
        els.recentFiles.addEventListener('change', function() { autoQuery(); });
        els.keyword.addEventListener('input', function() { autoQuery(); });
        els.folder.addEventListener('change', function() {
            var v = els.folder.value.trim();
            if (v) { notify('', ''); chipAdd(v, 'folder', v); }
        });
    }

    function bindFolderEvents() {
        els.folder.addEventListener('focus', function() {
            if (_justQueried) return;
            historyRender(historyLoad());
        });
        els.folder.addEventListener('blur', function() {
            setTimeout(function() { if (els.historyDropdown) els.historyDropdown.style.display = 'none'; }, 200);
        });

        // 历史项点击 (mousedown 比 blur 先触发)
        document.addEventListener('mousedown', function(e) {
            var item = e.target.closest('.history-item');
            if (item) {
                var folder = item.getAttribute('data-folder');
                if (folder) {
                    els.folder.value = folder;
                    els.historyDropdown.style.display = 'none';
                    chipAdd(folder, 'folder', folder);
                }
                return;
            }
            var dd = els.historyDropdown;
            if (dd && dd.style.display !== 'none') {
                if (!dd.contains(e.target) && e.target !== els.folder) {
                    dd.style.display = 'none';
                }
            }
        });

        // Escape 关闭下拉
        els.folder.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                if (els.historyDropdown) els.historyDropdown.style.display = 'none';
            }
        });
    }

    function bindButtonEvents() {
        els.btnQuery.addEventListener('click', function() {
            _justQueried = true; setTimeout(function() { _justQueried = false; }, 500);
            doQuery();
        });
        els.folder.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                _justQueried = true; setTimeout(function() { _justQueried = false; }, 500);
                if (els.historyDropdown) els.historyDropdown.style.display = 'none';
                doQuery();
            }
        });
    }

    // ════════════════════════════════════════════════════════════
    //  [API] 数据获取
    // ════════════════════════════════════════════════════════════

    function loadDateQueries() {
        fetch('/api/date-queries').then(function(r) { return r.json(); }).then(function(d) {
            _dateQueries = d.queries || [];
            renderDateQueries();
        }).catch(function() {
            els.dateQueriesContainer.innerHTML = '<div style="font-size:0.75rem;color:var(--text-tertiary);padding:4px">加载失败</div>';
            notify('快捷查询列表加载失败，请刷新页面', 'error');
        });
    }

    function fetchLogs(payload, callback) {
        var t0 = performance.now();
        fetch('/api/logs', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }).then(function(r) { return r.json(); }).then(function(data) {
            callback(null, data, Math.round(performance.now() - t0));
        }).catch(function(err) {
            callback(err);
        });
    }

    // ════════════════════════════════════════════════════════════
    //  [Render] 渲染层
    // ════════════════════════════════════════════════════════════

    /**
     * 共用：单行渲染（转义 → 高亮 → 规则注解）
     */
    function renderLine(content, file, keyword) {
        var escaped = escapeHtml(content);
        var rendered = keyword ? highlightKeyword(escaped, keyword) : escaped;
        if (typeof applyRulesAndAnnotations === 'function') {
            rendered = applyRulesAndAnnotations(rendered, file);
        }
        return rendered;
    }

    /**
     * 全量渲染：按文件分组
     */
    function renderResults(data, keyword, elapsedMs) {
        if (!data || !data.results || data.results.length === 0) {
            els.logResults.innerHTML = '<div class="empty-state">' +
                '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">' +
                '<circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>' +
                '<p>未找到匹配的日志内容' + (data.error ? '：' + escapeHtml(data.error) : '') + '</p></div>';
            els.queryTime.textContent = '';
            return;
        }

        var groups = {};
        data.results.forEach(function(item) {
            var fn = item.file || '?';
            if (!groups[fn]) groups[fn] = [];
            groups[fn].push(item);
        });
        var fileKeys = Object.keys(groups);

        var timeStr = elapsedMs < 1000 ? elapsedMs + 'ms' : (elapsedMs / 1000).toFixed(1) + 's';
        var truncatedBadge = data.truncated
            ? '<span class="stat-badge" style="color:var(--warning)">结果已截断</span>'
            : '<span class="stat-badge" style="color:var(--success)">结果完整</span>';
        var statsHtml = '<div class="result-stats">' +
            '<span class="stat-badge">共 ' + data.total_lines + ' 行</span>' +
            '<span class="stat-badge">' + fileKeys.length + ' 个文件</span>' +
            '<span class="stat-badge">⏱ ' + timeStr + '</span>' +
            truncatedBadge + '</div>';

        var bodyHtml = '';
        fileKeys.forEach(function(fn, fi) {
            var lines = groups[fn];
            var groupId = 'fg_' + fn.replace(/[^a-zA-Z0-9]/g, '_');
            bodyHtml += '<div class="file-group">' +
                '<div class="file-group-header" onclick="toggleFileGroup(\'' + groupId + '\')">' +
                '<span class="fg-arrow">▶</span><strong>' + escapeHtml(fn) + '</strong>' +
                '<span class="file-line-count">' + lines.length + ' 行</span>' +
                '<button class="btn-copy" onclick="event.stopPropagation();copyFileGroup(\'' + groupId + '\')">📋 复制</button>' +
                '</div>' +
                '<div class="file-group-body ' + (fi === 0 ? 'open' : '') + '" id="' + groupId + '">' +
                '<div class="log-table">';
            lines.forEach(function(item) {
                var rendered = renderLine(item.content, item.file, keyword);
                bodyHtml += '<div class="log-row">' +
                    '<span class="lr-line">' + item.line + '</span>' +
                    '<span class="lr-content">' + rendered + '</span></div>';
            });
            bodyHtml += '</div></div></div>';
        });

        els.logResults.innerHTML = statsHtml + bodyHtml;
        els.queryTime.textContent = '';
        showShellCmd(data.shell_cmd);
    }

    /**
     * 增量追加：新行追加到已有文件组（不移除旧内容）
     */
    function appendLiveLines(data, keyword) {
        if (!data || !data.results || data.results.length === 0) return false;
        var hasNew = false;
        data.results.forEach(function(item) {
            var fn = item.file || '?';
            if (!_seenLines[fn]) _seenLines[fn] = {};
            if (_seenLines[fn][item.line]) return;
            _seenLines[fn][item.line] = true;
            hasNew = true;

            var groupId = 'fg_' + fn.replace(/[^a-zA-Z0-9]/g, '_');
            var body = document.getElementById(groupId);
            if (!body) {
                body = createFileGroup(groupId, fn);
            }
            var rendered = renderLine(item.content, item.file, keyword);
            var row = document.createElement('div');
            row.className = 'log-row';
            row.innerHTML = '<span class="lr-line">' + item.line + '</span><span class="lr-content">' + rendered + '</span>';
            body.querySelector('.log-table').appendChild(row);
        });

        if (hasNew) {
            var container = document.getElementById('logScrollContainer');
            if (container) {
                var atBottom = (container.scrollHeight - container.scrollTop - container.clientHeight) < 200;
                if (atBottom) {
                    requestAnimationFrame(function() {
                        container.scrollTop = container.scrollHeight;
                    });
                }
            }
        }
        return hasNew;
    }

    function createFileGroup(groupId, fileName) {
        var group = document.createElement('div');
        group.className = 'file-group';
        group.innerHTML =
            '<div class="file-group-header" onclick="toggleFileGroup(\'' + groupId + '\')">' +
            '<span class="fg-arrow">▶</span><strong>' + escapeHtml(fileName) + '</strong>' +
            '<span class="file-line-count"></span>' +
            '<button class="btn-copy" onclick="event.stopPropagation();copyFileGroup(\'' + groupId + '\')">📋 复制</button>' +
            '</div>' +
            '<div class="file-group-body open" id="' + groupId + '"><div class="log-table"></div></div>';
        els.logResults.appendChild(group);
        return document.getElementById(groupId);
    }

    // ════════════════════════════════════════════════════════════
    //  [Query] 查询引擎
    // ════════════════════════════════════════════════════════════

    window.doQuery = function() {
        if (_queryLoading) return;
        var folder = els.folder.value.trim();
        if (!folder) {
            notify('请先输入日志路径再点击查询', 'warning');
            els.folder.focus();
            return;
        }

        notify('', '');
        _queryLoading = true;
        if (!_isLiveQuery) {
            els.btnQuery.innerHTML = '<span class="spinner" style="display:inline-block;width:14px;height:14px;border-width:2px;"></span> 查询中...';
            els.btnQuery.disabled = true;
            els.logResults.innerHTML = '<div class="empty-state"><div class="spinner"></div><p>查询中...</p></div>';
        }

        var keyword = els.keyword.value.trim() || null;
        if (!_isLiveQuery && _liveActive) {
            _liveKeyword = keyword;
        }
        var useKeyword = _isLiveQuery ? _liveKeyword : keyword;

        var payload = {
            folder: folder,
            pattern: els.pattern.value || '*.log',
            keyword: useKeyword,
            line_start: 1,
            line_end: parseInt(els.lineCount.value) || 50,
            tail: els.tail.value === 'true',
            recent_files: parseInt(els.recentFiles.value) || 2
        };

        if (!_isLiveQuery) historyAdd(folder);

        fetchLogs(payload, function(err, data, elapsed) {
            if (err) {
                if (!_isLiveQuery) {
                    els.logResults.innerHTML = '<div class="empty-state"><p style="color:var(--danger)">请求失败: ' + err.message + '</p></div>';
                    els.queryTime.textContent = '';
                }
            } else {
                if (_isLiveQuery) {
                    appendLiveLines(data, useKeyword);
                } else {
                    _seenLines = {};
                    if (data.results) data.results.forEach(function(item) {
                        var fn = item.file || '?';
                        if (!_seenLines[fn]) _seenLines[fn] = {};
                        _seenLines[fn][item.line] = true;
                    });
                    renderResults(data, useKeyword, elapsed);
                }
                if (_liveActive) {
                    _liveCountdown = LIVE_TIMEOUT;
                    _liveInterval = LIVE_INTERVAL_MIN;
                    updateLiveLabel(_liveCountdown, _liveInterval);
                    els.btnLive.classList.remove('auto-stop');
                    scheduleNext();
                }
            }
            _queryLoading = false;
            if (!_isLiveQuery) {
                els.btnQuery.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> 查询';
                els.btnQuery.disabled = false;
            }
        });
    };

    function doLiveQuery() {
        if (_queryLoading) return;
        var folder = els.folder.value.trim();
        if (!folder) return;

        _isLiveQuery = true;
        _queryLoading = true;

        var payload = {
            folder: folder,
            pattern: els.pattern.value || '*.log',
            keyword: _liveKeyword,
            line_start: 1,
            line_end: parseInt(els.lineCount.value) || 50,
            tail: els.tail.value === 'true',
            recent_files: parseInt(els.recentFiles.value) || 2
        };

        fetchLogs(payload, function(err, data) {
            if (!err) {
                var hadNew = appendLiveLines(data, _liveKeyword);
                if (_liveActive) {
                    if (hadNew) {
                        _liveInterval = LIVE_INTERVAL_MIN;
                        _liveCountdown = LIVE_TIMEOUT;
                    } else {
                        _liveInterval = Math.min(_liveInterval * 2, LIVE_INTERVAL_MAX);
                    }
                    updateLiveLabel(_liveCountdown, _liveInterval);
                    els.btnLive.classList.remove('auto-stop');
                    scheduleNext();
                }
            }
            _queryLoading = false;
            _isLiveQuery = false;
        });
    }

    // ════════════════════════════════════════════════════════════
    //  [Live] 实时轮询
    // ════════════════════════════════════════════════════════════

    function startLive() {
        if (_liveActive) return;
        _liveActive = true;
        _liveInterval = LIVE_INTERVAL_MIN;
        els.btnLive.classList.add('active');
        els.btnLive.classList.remove('auto-stop');
        _liveCountdown = LIVE_TIMEOUT;
        updateLiveLabel(_liveCountdown, _liveInterval);
        clearInterval(_liveCountdownId);
        _liveCountdownId = setInterval(tickCountdown, 1000);
        // 先做一次全量查询
        doQuery();
    }

    function stopLive() {
        _liveActive = false;
        _isLiveQuery = false;
        clearTimeout(_liveTimer);
        clearInterval(_liveCountdownId);
        els.btnLive.classList.remove('active', 'auto-stop');
        _liveInterval = LIVE_INTERVAL_MIN;
        updateLiveLabel(0, _liveInterval);
    }

    function scheduleNext() {
        clearTimeout(_liveTimer);
        if (!_liveActive) return;
        _liveTimer = setTimeout(function() {
            if (!_liveActive) return;
            doLiveQuery();
        }, _liveInterval);
    }

    function tickCountdown() {
        if (!_liveActive) return;
        _liveCountdown--;
        updateLiveLabel(_liveCountdown, _liveInterval);
        if (_liveCountdown <= 0) stopLive();
    }

    function updateLiveLabel(sec, interval) {
        if (!els.btnLiveLabel) return;
        var ivSec = interval || _liveInterval;
        var ivStr = (ivSec >= 1000) ? (ivSec / 1000).toFixed(0) + 's' : '';
        if (sec > 0) {
            els.btnLiveLabel.textContent = '滚动 ' + ivStr + ' (' + sec + 's)';
            if (sec <= 10) els.btnLive.classList.add('auto-stop');
        } else {
            els.btnLiveLabel.textContent = '滚动';
        }
    }

    window.toggleLive = function() {
        if (_liveActive) {
            stopLive();
        } else {
            var hasResults = document.querySelector('.file-group');
            if (hasResults) {
                startLive();
                doLiveQuery();
            } else {
                startLive();
            }
        }
    };

    // ════════════════════════════════════════════════════════════
    //  [Utils] 工具函数
    // ════════════════════════════════════════════════════════════

    // ── 气泡筛选
    function chipAdd(label, field, value) {
        var cid = 'chip_' + field;
        if (document.getElementById(cid)) return;
        var chip = document.createElement('span');
        chip.className = 'chip'; chip.id = cid;
        chip.setAttribute('data-field', field);
        chip.setAttribute('data-value', value);
        chip.innerHTML = escapeHtml(label) + '<button class="chip-x" onclick="this.parentNode.remove();autoQuery();">&times;</button>';
        els.chipFilters.appendChild(chip);
        if (field === 'folder') els.folder.value = value;
        if (field === 'pattern') els.pattern.value = value;
        if (field === 'keyword') els.keyword.value = value;
        autoQuery();
    }

    function chipClearAll() { els.chipFilters.innerHTML = ''; }

    // ── 自动查询（防抖 500ms）
    function autoQuery() {
        clearTimeout(_debounceTimer);
        _debounceTimer = setTimeout(function() { if (_liveActive) { stopLive(); } doQuery(); }, 500);
    }

    // ── 搜索历史
    function historyLoad() {
        try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch(e) { return []; }
    }
    function historySave(h) {
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(h.slice(0, MAX_HISTORY))); } catch(e) {}
    }
    function historyAdd(folder) {
        var h = historyLoad();
        var idx = h.findIndex(function(e) { return e.folder === folder; });
        if (idx !== -1) h.splice(idx, 1);
        h.unshift({ folder: folder, time: Date.now() });
        historySave(h);
        historyRender(h);
    }
    function historyRender(h) {
        var el = els.historyDropdown; if (!el) return;
        if (!h || h.length === 0) { el.style.display = 'none'; return; }
        var html = '', shown = {};
        h.forEach(function(e) {
            if (shown[e.folder]) return; shown[e.folder] = true;
            html += '<div class="history-item" data-folder="' + e.folder.replace(/"/g,'&quot;') + '">' +
                '<span class="history-path">' + escapeHtml(e.folder) + '</span></div>';
        });
        el.innerHTML = html;
        el.style.display = 'block';
    }

    // ── Shell 命令展示
    function showShellCmd(cmd) {
        if (!els.shellCmdBar || !els.shellCmdText) return;
        if (!cmd) { els.shellCmdBar.style.display = 'none'; return; }
        _lastShellCmd = cmd;
        els.shellCmdText.textContent = '$ ' + cmd;
        els.shellCmdBar.style.display = 'flex';
    }

    window.copyShellCmd = function() {
        if (!_lastShellCmd) return;
        navigator.clipboard.writeText(_lastShellCmd).catch(function(){});
        var ta = document.createElement('textarea');
        ta.value = _lastShellCmd; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        document.execCommand('copy'); document.body.removeChild(ta);
    };

    window.toggleFileGroup = function(groupId) {
        var body = document.getElementById(groupId);
        if (body) body.classList.toggle('open');
    };

    window.copyFileGroup = function(groupId) {
        var body = document.getElementById(groupId);
        if (!body) return;
        var lines = [];
        body.querySelectorAll('.lr-content').forEach(function(el) { lines.push(el.textContent); });
        var text = lines.join('\n');
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).catch(function(){});
        }
        var ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        document.execCommand('copy'); document.body.removeChild(ta);
    };

    window.resetFilters = function() {
        stopLive();
        _seenLines = {};
        els.folder.value = '';
        els.pattern.value = '*.log';
        els.keyword.value = '';
        els.lineCount.value = '50';
        els.tail.value = 'true';
        els.recentFiles.value = '2';
        chipClearAll();
        if (els.shellCmdBar) els.shellCmdBar.style.display = 'none';
        els.logResults.innerHTML = '<div class="empty-state">' +
            '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">' +
            '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>' +
            '<p>输入查询条件后点击"查询"查看日志</p></div>';
        els.queryTime.textContent = '';
    };

    // ════════════════════════════════════════════════════════════
    //  [Feedback] 统一通知
    // ════════════════════════════════════════════════════════════

    var _feedbackTimer = null;

    function notify(msg, type) {
        var el = document.getElementById('feedbackMsg');
        if (!el) return;
        if (!msg) { el.style.display = 'none'; return; }
        el.textContent = msg;
        el.style.color = type === 'warning' ? 'var(--warning, #f59e0b)'
            : type === 'error' ? 'var(--danger, #ef4444)'
            : type === 'ok' ? 'var(--success, #22c55e)'
            : 'var(--text-secondary)';
        el.style.display = 'block';
        clearTimeout(_feedbackTimer);
        _feedbackTimer = setTimeout(function() { el.style.display = 'none'; }, 3000);
    }

    // ════════════════════════════════════════════════════════════
    //  [Date Queries] 快捷查询管理
    // ════════════════════════════════════════════════════════════

    function renderDateQueries() {
        var container = els.dateQueriesContainer;
        if (!container) return;
        if (_dateQueries.length === 0) {
            container.innerHTML = '<div style="font-size:0.75rem;color:var(--text-tertiary);padding:4px">暂无保存</div>';
            return;
        }
        var html = '';
        _dateQueries.forEach(function(q, i) {
            var tooltip = (q.desc ? q.desc + ' | ' : '') + (q.folder || '?') + (q.keyword ? ' · ' + q.keyword : '');
            html += '<div class="dq-item" data-idx="' + i + '" title="' + escapeHtml(tooltip) + '">' +
                '<span class="dq-name">' + escapeHtml(q.name || '?') + '</span>' +
                '<button class="dq-delete" data-idx="' + i + '" title="删除">✕</button></div>';
        });
        container.innerHTML = html;
    }

    function applyDateQuery(q) {
        if (q.folder) els.folder.value = q.folder;
        if (q.pattern) els.pattern.value = q.pattern;
        if (q.keyword) els.keyword.value = q.keyword;
        if (q.line_count) els.lineCount.value = String(q.line_count);
        if (q.tail !== undefined && q.tail !== null) els.tail.value = q.tail ? 'true' : 'false';
        if (q.recent_files) els.recentFiles.value = String(q.recent_files);
        stopLive();
        chipClearAll();
        if (q.folder) chipAdd(q.name || q.folder, 'folder', q.folder);
        doQuery();
    }

    window.openSaveDialog = function() {
        var folder = els.folder.value.trim();
        if (!folder) {
            notify('请先输入日志路径后再保存快捷查询', 'warning');
            els.folder.focus();
            return;
        }
        _editingFilename = null;
        document.getElementById('saveName').value = '';
        document.getElementById('saveDesc').value = '';
        document.getElementById('saveOverlay').style.display = 'flex';
    };

    window.closeSaveDialog = function() {
        document.getElementById('saveOverlay').style.display = 'none';
        _editingFilename = null;
    };

    window.doSaveQuery = function() {
        var name = document.getElementById('saveName').value.trim();
        if (!name) { notify('请输入查询名称', 'warning'); return; }
        var folder = els.folder.value.trim();
        if (!folder) { notify('请先选择日志路径', 'warning'); return; }

        var btn = document.getElementById('btnSaveConfirm');
        btn.disabled = true;
        btn.textContent = '保存中...';

        var payload = {
            name: name,
            folder: folder,
            pattern: els.pattern.value || '*.log',
            keyword: els.keyword.value.trim(),
            line_count: parseInt(els.lineCount.value) || 50,
            tail: els.tail.value === 'true',
            recent_files: parseInt(els.recentFiles.value) || 2,
            desc: document.getElementById('saveDesc').value.trim(),
        };
        if (_editingFilename) payload.filename = _editingFilename;

        fetch('/api/date-queries', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }).then(function(r) { return r.json(); }).then(function(d) {
            _dateQueries = d.queries || [];
            renderDateQueries();
            closeSaveDialog();
            notify('快捷查询「' + escapeHtml(name) + '」已保存', 'ok');
        }).catch(function(err) {
            notify('保存失败: ' + err.message, 'error');
        }).finally(function() {
            btn.disabled = false;
            btn.textContent = '保存';
        });
    };

    function deleteDateQuery(idx) {
        var q = _dateQueries[idx];
        if (!q) return;
        var filename = q.filename;
        if (!filename) return;
        if (!confirm('确定删除快捷查询「' + q.name + '」？')) return;

        fetch('/api/date-queries/' + encodeURIComponent(filename), { method: 'DELETE' })
            .then(function(r) { return r.json(); })
            .then(function(d) {
                _dateQueries = d.queries || [];
                renderDateQueries();
            }).catch(function(err) {
                notify('删除失败: ' + err.message, 'error');
            });
    }

})();

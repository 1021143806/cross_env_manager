/**
 * postlook · 日志查询 v2 — 自动查询 + 气泡筛选 + 分组折叠 + 耗时统计
 */
(function() {
    var queryLoading = false;
    var STORAGE_KEY = 'postlook-search-history-v2';
    var MAX_HISTORY = 15;
    var _debounceTimer = null;
    var _liveTimer = null, _liveCountdown = null;
    var _liveActive = false;
    var LIVE_INTERVAL = 3000;      // 刷新间隔 3s
    var LIVE_TIMEOUT = 60;         // 自动关闭倒计时 60s
    var _seenLines = {};           // 已显示行号: { filename: Set(lineNumber) }
    var _liveKeyword = null;       // 实时模式下首次查询的关键字（后续保持不变）
    var _isLiveQuery = false;      // 标记当前是否为实时增量查询

    // ── DOM 引用 ──
    var els = {};
    function cacheEls() {
        ['folder','pattern','keyword','lineCount','tail','recentFiles',
         'chipFilters','btnQuery','btnLive','btnLiveLabel','queryTime','logResults','historyDropdown','rulesContainer'].forEach(function(id) {
            els[id] = document.getElementById(id);
        });
    }

    // ── 搜索历史 ──
    function historyLoad() { try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch(e) { return []; } }
    function historySave(h) { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(h.slice(0, MAX_HISTORY))); } catch(e) {} }

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
        var html = '';
        var shown = {};
        h.forEach(function(e) {
            if (shown[e.folder]) return; shown[e.folder] = true;
            html += '<div class="history-item" data-folder="' + e.folder.replace(/"/g,'&quot;') + '">' +
                '<span class="history-path">' + escapeHtml(e.folder) + '</span></div>';
        });
        el.innerHTML = html;
        el.style.display = 'block';
    }

    // ── 气泡筛选 ──
    function chipAdd(label, field, value) {
        var cid = 'chip_' + field;
        if (document.getElementById(cid)) return; // 同字段不重复
        var chip = document.createElement('span');
        chip.className = 'chip'; chip.id = cid;
        chip.setAttribute('data-field', field);
        chip.setAttribute('data-value', value);
        chip.innerHTML = escapeHtml(label) + '<button class="chip-x" onclick="this.parentNode.remove();autoQuery();">&times;</button>';
        els.chipFilters.appendChild(chip);
        // 更新原始控件
        if (field === 'folder') els.folder.value = value;
        if (field === 'pattern') els.pattern.value = value;
        if (field === 'keyword') els.keyword.value = value;
        autoQuery();
    }

    function chipClearAll() { els.chipFilters.innerHTML = ''; }

    // ── 自动查询（防抖 500ms） ──
    function autoQuery() {
        clearTimeout(_debounceTimer);
        _debounceTimer = setTimeout(function() { stopLive(); doQuery(); }, 500);
    }

    function autoQueryImmediate() {
        clearTimeout(_debounceTimer);
        stopLive();
        doQuery();
    }

    // ── 实时刷新 ──
    function startLive() {
        if (_liveActive) return;
        _liveActive = true;
        els.btnLive.style.display = 'inline-flex';
        els.btnLive.classList.add('active');
        els.btnLive.classList.remove('auto-stop');
        _liveCountdown = LIVE_TIMEOUT;
        updateLiveLabel(_liveCountdown);
        // 倒计时 ticker
        clearInterval(_liveCountdownId);
        _liveCountdownId = setInterval(tickCountdown, 1000);
        scheduleNext();
    }

    function stopLive() {
        _liveActive = false;
        clearTimeout(_liveTimer);
        clearInterval(_liveCountdownId);
        els.btnLive.classList.remove('active','auto-stop');
        updateLiveLabel(0);
        els.btnLive.style.display = 'none';
    }

    window.toggleLive = function() {
        if (_liveActive) {
            stopLive();
        } else {
            // 已有结果则直接增量，否则先做一次全量
            var hasResults = document.querySelector('.file-group');
            if (hasResults) {
                startLive();
                doLiveQuery();
            } else {
                startLive();
                doQuery();
            }
        }
    }

    var _liveCountdownId = null;
    function scheduleNext() {
        clearTimeout(_liveTimer);
        if (!_liveActive) return;
        _liveTimer = setTimeout(function() {
            if (!_liveActive) return;
            doLiveQuery();
        }, LIVE_INTERVAL);
    }

    function startLive() {
        if (_liveActive) return;
        _liveActive = true;
        els.btnLive.classList.add('active');
        els.btnLive.classList.remove('auto-stop');
        _liveCountdown = LIVE_TIMEOUT;
        updateLiveLabel(_liveCountdown);
        clearInterval(_liveCountdownId);
        _liveCountdownId = setInterval(tickCountdown, 1000);
        // 先做一次全量查询，然后增量
        doQuery();
    }

    function stopLive() {
        _liveActive = false;
        _isLiveQuery = false;
        clearTimeout(_liveTimer);
        clearInterval(_liveCountdownId);
        els.btnLive.classList.remove('active','auto-stop');
        updateLiveLabel(0);
    }

    function updateLiveLabel(sec) {
        if (sec > 0) {
            els.btnLiveLabel.textContent = '滚动 (' + sec + 's)';
            if (sec <= 10) els.btnLive.classList.add('auto-stop');
        } else {
            els.btnLiveLabel.textContent = '滚动';
        }
    }

    function tickCountdown() {
        if (!_liveActive) return;
        _liveCountdown--;
        updateLiveLabel(_liveCountdown);
        if (_liveCountdown <= 0) {
            stopLive();
        }
    }

    // ── 执行全量查询（刷新整个结果区）──
    function doQuery() {
        if (queryLoading) return;
        var folder = els.folder.value.trim();
        if (!folder) return;

        queryLoading = true;
        if (!_isLiveQuery) {
            els.btnQuery.innerHTML = '<span class="spinner" style="display:inline-block;width:14px;height:14px;border-width:2px;"></span> 查询中...';
            els.btnQuery.disabled = true;
            els.logResults.innerHTML = '<div class="empty-state"><div class="spinner"></div><p>查询中...</p></div>';
        }

        var keyword = els.keyword.value.trim() || null;
        // 实时模式下：首次查询记录关键字，后续沿用（避免关键字变化导致行号错乱）
        if (!_isLiveQuery && _liveActive) {
            _liveKeyword = keyword;
        }
        var useKeyword = _isLiveQuery ? _liveKeyword : keyword;

        var payload = {
            folder: folder,
            pattern: els.pattern.value || '*.log',
            keyword: useKeyword,
            line_start: 1,
            line_end: parseInt(els.lineCount.value) || 100,
            tail: els.tail.value === 'true',
            recent_files: parseInt(els.recentFiles.value) || 2
        };

        if (!_isLiveQuery) historyAdd(folder);

        var t0 = performance.now();
        fetch('/api/logs', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }).then(function(r) { return r.json(); }).then(function(data) {
            var elapsed = Math.round(performance.now() - t0);
            if (_isLiveQuery) {
                appendLiveLines(data, useKeyword);
            } else {
                // 记录已显示行
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
                updateLiveLabel(_liveCountdown);
                els.btnLive.classList.remove('auto-stop');
                scheduleNext();
            }
        }).catch(function(err) {
            if (!_isLiveQuery) {
                els.logResults.innerHTML = '<div class="empty-state"><p style="color:var(--danger)">请求失败: ' + err.message + '</p></div>';
                els.queryTime.textContent = '';
            }
        }).finally(function() {
            queryLoading = false;
            if (!_isLiveQuery) {
                els.btnQuery.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> 查询';
                els.btnQuery.disabled = false;
            }
        });
    }

    // ── 实时增量查询（静默，不清屏）──
    function doLiveQuery() {
        if (queryLoading) return;
        var folder = els.folder.value.trim();
        if (!folder) return;

        _isLiveQuery = true;
        queryLoading = true;

        var payload = {
            folder: folder,
            pattern: els.pattern.value || '*.log',
            keyword: _liveKeyword,
            line_start: 1,
            line_end: parseInt(els.lineCount.value) || 100,
            tail: els.tail.value === 'true',
            recent_files: parseInt(els.recentFiles.value) || 2
        };

        fetch('/api/logs', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }).then(function(r) { return r.json(); }).then(function(data) {
            appendLiveLines(data, _liveKeyword);
            if (_liveActive) {
                _liveCountdown = LIVE_TIMEOUT;
                updateLiveLabel(_liveCountdown);
                els.btnLive.classList.remove('auto-stop');
                scheduleNext();
            }
        }).catch(function(err) {
            // 静默失败，不影响界面
        }).finally(function() {
            queryLoading = false;
            _isLiveQuery = false;
        });
    }

    // ── 增量追加新行到已有结果 ──
    function appendLiveLines(data, keyword) {
        if (!data || !data.results || data.results.length === 0) return;
        var hasNew = false;
        data.results.forEach(function(item) {
            var fn = item.file || '?';
            if (!_seenLines[fn]) _seenLines[fn] = {};
            if (_seenLines[fn][item.line]) return;  // 已显示过，跳过
            _seenLines[fn][item.line] = true;
            hasNew = true;
            var groupId = 'fg_' + fn.replace(/[^a-zA-Z0-9]/g, '_');
            var body = document.getElementById(groupId);
            if (!body) {
                // 新文件：创建文件组
                body = createFileGroup(groupId, fn);
            }
            var content = escapeHtml(item.content);
            var rendered = keyword ? highlightKeyword(content, keyword) : content;
            rendered = applyRulesAndAnnotations(rendered, item.file);
            var row = document.createElement('div');
            row.className = 'log-row';
            row.innerHTML = '<span class="lr-line">' + item.line + '</span><span class="lr-content">' + rendered + '</span>';
            body.querySelector('.log-table').appendChild(row);
        });
        if (hasNew) {
            var lastRow = document.querySelector('.log-row:last-child');
            if (lastRow && lastRow.scrollIntoView) lastRow.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }
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

    window.toggleFileGroup = function(groupId) {
        var body = document.getElementById(groupId);
        if (body) body.classList.toggle('open');
    };

    // ── 渲染结果：按文件分组 ──
    function renderResults(data, keyword, elapsedMs) {
        if (!data || !data.results || data.results.length === 0) {
            els.logResults.innerHTML = '<div class="empty-state">' +
                '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">' +
                '<circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>' +
                '<p>未找到匹配的日志内容' + (data.error ? '：' + escapeHtml(data.error) : '') + '</p></div>';
            els.queryTime.textContent = '';
            return;
        }

        // 按 file 分组
        var groups = {};
        data.results.forEach(function(item) {
            var fn = item.file || '?';
            if (!groups[fn]) groups[fn] = [];
            groups[fn].push(item);
        });
        var fileKeys = Object.keys(groups);

        // 统计栏
        var timeStr = elapsedMs < 1000 ? elapsedMs + 'ms' : (elapsedMs / 1000).toFixed(1) + 's';
        var truncatedBadge = data.truncated
            ? '<span class="stat-badge" style="color:var(--warning)">结果已截断</span>'
            : '<span class="stat-badge" style="color:var(--success)">结果完整</span>';
        var statsHtml = '<div class="result-stats">' +
            '<span class="stat-badge">共 ' + data.total_lines + ' 行</span>' +
            '<span class="stat-badge">' + fileKeys.length + ' 个文件</span>' +
            '<span class="stat-badge">\u23F1 ' + timeStr + '</span>' +
            truncatedBadge +
            '</div>';

        // 文件分组
        var bodyHtml = '';
        fileKeys.forEach(function(fn, fi) {
            var lines = groups[fn];
            var groupId = 'fg_' + fn.replace(/[^a-zA-Z0-9]/g, '_');
            bodyHtml += '<div class="file-group">' +
                '<div class="file-group-header" onclick="toggleFileGroup(\'' + groupId + '\')">' +
                '<span class="fg-arrow">\u25B6</span><strong>' + escapeHtml(fn) + '</strong>' +
                '<span class="file-line-count">' + lines.length + ' 行</span>' +
                '<button class="btn-copy" onclick="event.stopPropagation();copyFileGroup(\'' + groupId + '\')">\uD83D\uDCCB 复制</button>' +
                '</div>' +
                '<div class="file-group-body ' + (fi === 0 ? 'open' : '') + '" id="' + groupId + '">' +
                '<div class="log-table">';
            lines.forEach(function(item) {
                var content = escapeHtml(item.content);
                var rendered = keyword ? highlightKeyword(content, keyword) : content;
                rendered = applyRulesAndAnnotations(rendered, item.file);
                bodyHtml += '<div class="log-row">' +
                    '<span class="lr-line">' + item.line + '</span>' +
                    '<span class="lr-content">' + rendered + '</span></div>';
            });
            bodyHtml += '</div></div></div>';
        });

        els.logResults.innerHTML = statsHtml + bodyHtml;
        els.queryTime.textContent = '';
    }

    // ── 复制文件分组内容 ──
    window.copyFileGroup = function(groupId) {
        var body = document.getElementById(groupId);
        if (!body) return;
        var lines = [];
        body.querySelectorAll('.lr-content').forEach(function(el) { lines.push(el.textContent); });
        var text = lines.join('\n');
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(function() { /* ok */ }).catch(function() {});
        }
        // fallback
        var ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        document.execCommand('copy'); document.body.removeChild(ta);
    };

    // ── 重置 ──
    window.resetFilters = function() {
        stopLive();
        _seenLines = {};
        els.folder.value = '';
        els.pattern.value = '*.log';
        els.keyword.value = '';
        els.lineCount.value = '100';
        els.tail.value = 'true';
        els.recentFiles.value = '2';
        chipClearAll();
        els.logResults.innerHTML = '<div class="empty-state">' +
            '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">' +
            '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>' +
            '<p>输入查询条件后点击"查询"查看日志</p></div>';
        els.queryTime.textContent = '';
    };

    // ── 初始化 ──
    document.addEventListener('DOMContentLoaded', function() {
        cacheEls();

        // 规则加载
        loadRules(function(rules) {
            var container = els.rulesContainer;
            if (!container) return;
            var queryRules = rules.filter(function(r) { return r.folder; });
            if (queryRules.length === 0) {
                container.innerHTML = '<div style="font-size:0.75rem;color:var(--text-tertiary);padding:4px">无规则</div>';
                return;
            }
            var html = '';
            queryRules.forEach(function(rule, i) {
                html += '<button class="sb-btn rule-btn" title="' + (rule.desc || '') + '" data-idx="' + i + '">' + (rule.name || '?') + '</button>';
            });
            container.innerHTML = html;

            // 绑定规则点击
            container.addEventListener('click', function(e) {
                var btn = e.target.closest('.rule-btn');
                if (!btn) return;
                var idx = parseInt(btn.getAttribute('data-idx'));
                var rule = queryRules[idx];
                if (!rule) return;
                if (rule.folder) els.folder.value = rule.folder;
                if (rule.pattern) els.pattern.value = rule.pattern;
                if (rule.match) els.keyword.value = rule.match;
                if (rule.folder) chipAdd(rule.name || rule.folder, 'folder', rule.folder);
                autoQueryImmediate();
            });
        });

        // 历史记录
        els.folder.addEventListener('focus', function() {
            historyRender(historyLoad());
        });
        els.folder.addEventListener('blur', function() {
            setTimeout(function() { if (els.historyDropdown) els.historyDropdown.style.display = 'none'; }, 200);
        });
        document.addEventListener('click', function(e) {
            var item = e.target.closest('.history-item');
            if (!item) return;
            var folder = item.getAttribute('data-folder');
            if (folder) {
                els.folder.value = folder;
                els.historyDropdown.style.display = 'none';
                chipAdd(folder, 'folder', folder);
            }
        });

        // 自动查询：下拉/输入变化
        els.pattern.addEventListener('change', function() { autoQuery(); });
        els.lineCount.addEventListener('change', function() { autoQuery(); });
        els.tail.addEventListener('change', function() { autoQuery(); });
        els.recentFiles.addEventListener('change', function() { autoQuery(); });
        els.keyword.addEventListener('input', function() { autoQuery(); });
        els.folder.addEventListener('change', function() {
            var v = els.folder.value.trim();
            if (v) { chipAdd(v, 'folder', v); }
        });

        // 查询按钮
        els.btnQuery.addEventListener('click', function() { doQuery(); });

        // 回车快捷
        els.folder.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') { e.preventDefault(); doQuery(); }
        });
    });
})();

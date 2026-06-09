/**
 * postlook · 日志查询页面逻辑
 */
document.addEventListener('DOMContentLoaded', function() {
    var logForm = document.getElementById('logForm');
    var logResults = document.getElementById('logResults');
    var queryLoading = false;

    // ── 搜索历史 ──
    var STORAGE_KEY = 'postlook-search-history';
    var MAX_HISTORY = 15;
    var folderInput = document.getElementById('folder');

    function loadHistory() {
        try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch(e) { return []; }
    }

    function saveHistory(h) {
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(h.slice(0, MAX_HISTORY))); } catch(e) {}
    }

    function addHistory(folder, keyword) {
        var h = loadHistory();
        // 去重（同 folder+keyword 的移到最前）
        var idx = h.findIndex(function(e) { return e.folder === folder && e.keyword === keyword; });
        if (idx !== -1) h.splice(idx, 1);
        h.unshift({ folder: folder, keyword: keyword || '', time: Date.now() });
        saveHistory(h);
        renderHistoryDropdown(h);
    }

    function renderHistoryDropdown(h) {
        var el = document.getElementById('searchHistoryDropdown');
        if (!el) return;
        if (h.length === 0) { el.style.display = 'none'; return; }
        var html = '';
        var shown = {};
        h.forEach(function(e) {
            if (shown[e.folder]) return;
            shown[e.folder] = true;
            html += '<div class="history-item" data-folder="' + e.folder.replace(/"/g,'&quot;') + '" data-keyword="' + (e.keyword||'').replace(/"/g,'&quot;') + '">' +
                '<span class="history-path">' + escapeHtml(e.folder) + '</span>' +
                (e.keyword ? '<span class="history-keyword">' + escapeHtml(e.keyword) + '</span>' : '') +
                '</div>';
        });
        el.innerHTML = html;
        el.style.display = html ? 'block' : 'none';
    }

    // 显示/隐藏历史下拉
    folderInput.addEventListener('focus', function() {
        var h = loadHistory();
        renderHistoryDropdown(h);
    });
    folderInput.addEventListener('blur', function() {
        setTimeout(function() {
            var el = document.getElementById('searchHistoryDropdown');
            if (el) el.style.display = 'none';
        }, 200);
    });
    // 点击历史项
    document.addEventListener('click', function(e) {
        var item = e.target.closest('.history-item');
        if (!item) return;
        var folder = item.getAttribute('data-folder');
        var keyword = item.getAttribute('data-keyword');
        if (folder) document.getElementById('folder').value = folder;
        if (keyword) document.getElementById('keyword').value = keyword;
        document.getElementById('searchHistoryDropdown').style.display = 'none';
        // 自动提交
        setTimeout(function() {
            logForm.dispatchEvent(new Event('submit', {cancelable: true, bubbles: true}));
        }, 150);
    });

    // 表单提交
    logForm.addEventListener('submit', function(e) {
        e.preventDefault();
        if (queryLoading) return;

        var formData = new FormData(logForm);
        var folder = formData.get('folder');
        var keyword = formData.get('keyword') || '';
        var payload = {
            folder: folder,
            pattern: formData.get('pattern') || '*.log',
            keyword: keyword || null,
            line_start: parseInt(formData.get('line_start')) || 1,
            line_end: parseInt(formData.get('line_end')) || 100,
            tail: formData.get('tail') === 'true',
            recent_files: parseInt(formData.get('recent_files')) || 10
        };

        // 保存搜索历史
        if (folder) addHistory(folder, keyword);

        // 加载状态
        queryLoading = true;
        logResults.innerHTML = '<div class="results-placeholder"><div class="spinner"></div><p>查询中...</p></div>';

        fetch('/api/logs', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }).then(function(r){return r.json();}).then(function(data){
            renderLogResults(data, payload.keyword);
        }).catch(function(err){
            logResults.innerHTML = '<div class="results-placeholder"><p style="color:var(--danger)">请求失败: ' + err.message + '</p></div>';
        }).finally(function(){
            queryLoading = false;
        });
    });

    // 渲染结果
    function renderLogResults(data, keyword) {
        if (!data || !data.results || data.results.length === 0) {
            logResults.innerHTML = '<div class="results-placeholder">' +
                '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">' +
                '<circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/>' +
                '</svg><p>未找到匹配的日志内容' + (data.error ? '：' + data.error : '') + '</p></div>';
            return;
        }

        var truncatedBadge = data.truncated
            ? '<span class="badge badge-truncated">结果已截断</span>'
            : '<span class="badge badge-complete">结果完整</span>';

        var html = '<div class="results-summary"><span>共找到 <strong>' + data.total_lines + '</strong> 条匹配行</span>' + truncatedBadge + '</div>';
        html += '<div class="log-table">';

        data.results.forEach(function(item) {
            var content = escapeHtml(item.content);
            // ① 搜索关键字高亮
            var rendered = keyword ? highlightKeyword(content, keyword) : content;
            // ② 规则着色 + 注解
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

    // 规则按钮点击
    document.getElementById('rulesContainer').addEventListener('click', function(e) {
        var btn = e.target.closest('.rule-btn');
        if (!btn) return;
        var idx = parseInt(btn.getAttribute('data-rule-idx'));
        var rule = (typeof window._allRules !== 'undefined') ? window._allRules[idx] : null;
        if (!rule) return;
        if (rule.folder) document.getElementById('folder').value = rule.folder;
        if (rule.pattern) document.getElementById('pattern').value = rule.pattern;
        if (rule.match) document.getElementById('keyword').value = rule.match;
        if (rule.line_start) document.getElementById('line_start').value = rule.line_start;
        if (rule.line_end) document.getElementById('line_end').value = rule.line_end;
        setTimeout(function() {
            logForm.dispatchEvent(new Event('submit', {cancelable: true, bubbles: true}));
        }, 150);
    });

    // 加载规则
    loadRules(function(rules) {
        var container = document.getElementById('rulesContainer');
        if (!container) return;
        window._allRules = rules;
        var queryRules = rules.filter(function(r){ return r.folder; });
        if (queryRules.length === 0) {
            container.innerHTML = '<div style="font-size:0.75rem;color:var(--text-tertiary);padding:4px">无规则</div>';
            return;
        }
        var html = '';
        queryRules.forEach(function(rule) {
            var origIdx = rules.indexOf(rule);
            html += '<button class="sb-btn rule-btn" title="'+(rule.desc||'')+'" data-rule-idx="'+origIdx+'">'+(rule.name||'?')+'</button>';
        });
        container.innerHTML = html;
    });
});

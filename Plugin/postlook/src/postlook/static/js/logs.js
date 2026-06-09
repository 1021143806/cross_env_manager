/**
 * postlook · 日志查询页面逻辑
 */
document.addEventListener('DOMContentLoaded', function() {
    var logForm = document.getElementById('logForm');
    var logResults = document.getElementById('logResults');
    var queryLoading = false;

    // 表单提交
    logForm.addEventListener('submit', function(e) {
        e.preventDefault();
        if (queryLoading) return;
        queryLoading = true;

        var formData = new FormData(logForm);
        var payload = {
            folder: formData.get('folder'),
            pattern: formData.get('pattern') || '*.log',
            keyword: formData.get('keyword') || null,
            line_start: parseInt(formData.get('line_start')) || 1,
            line_end: parseInt(formData.get('line_end')) || 100,
            tail: formData.get('tail') === 'true',
            recent_files: parseInt(formData.get('recent_files')) || 10
        };

        // 加载状态
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

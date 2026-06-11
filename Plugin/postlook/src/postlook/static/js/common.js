/**
 * postlook · 公共工具函数
 * 所有页面共享：主题切换、HTML 转义、高亮、规则渲染
 */

// ── 主题 + Embed 模式 ──
(function() {
    var html = document.documentElement;
    var isEmbed = location.search.includes('embed=1');
    if (isEmbed) html.classList.add('embed-mode');

    var savedTheme = localStorage.getItem('postlook-theme');
    if (savedTheme) html.setAttribute('data-theme', savedTheme);

    document.addEventListener('DOMContentLoaded', function() {
        // Embed 模式：不绑定主题按钮，监听 postMessage
        if (isEmbed) {
            window.addEventListener('message', function(e) {
                if (e.data && e.data.type === 'setTheme') {
                    html.setAttribute('data-theme', e.data.value);
                }
            });
            return;
        }

        var themeBtn = document.getElementById('themeBtn');
        if (!themeBtn) return;
        themeBtn.addEventListener('click', function() {
            var current = html.getAttribute('data-theme');
            var next = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', next);
            localStorage.setItem('postlook-theme', next);
        });
    });
})();

// ── HTML 转义 ──
function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ── 关键字高亮 ──
function highlightKeyword(text, keyword) {
    if (!keyword) return text;
    var escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    var regex = new RegExp('(' + escaped + ')', 'gi');
    return text.replace(regex, '<span class="highlight">$1</span>');
}

// ── 规则编译（着色/注解） ──
var compiledRules = [];

function compileRule(rule) {
    var c = {
        type: rule.type || 'keyword',
        color: rule.color || null,
        background: rule.background || null,
        bold: rule.bold || false,
        annotation: rule.annotation || null,
        match: rule.match || '',
        name: rule.name || ''
    };
    if (rule.file) {
        c.filePattern = new RegExp(rule.file.replace(/\*/g, '.*').replace(/\?/g, '.'), 'i');
    } else {
        c.filePattern = null;
    }
    if (c.type === 'hex') {
        c.normalizedHex = rule.match.replace(/\s+/g, '').toLowerCase();
    } else if (c.type === 'regex') {
        c.compiledRegex = new RegExp(rule.match, 'gi');
    } else {
        c.compiledRegex = new RegExp('(' + rule.match.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
    }
    return c;
}

function loadRules(callback) {
    fetch('/api/rules').then(function(r){return r.json();}).then(function(data){
        var rules = data.rules || [];
        compiledRules = [];
        rules.forEach(function(r) { compiledRules.push(compileRule(r)); });
        if (callback) callback(rules);
    }).catch(function(){
        if (callback) callback([]);
    });
}

// ── 着色 + 注解 ──
function applyRulesAndAnnotations(content, file) {
    if (!compiledRules || compiledRules.length === 0) return content;

    var annotations = [];
    var wrapped = false;

    compiledRules.forEach(function(rule) {
        if (rule.filePattern && file && !rule.filePattern.test(file)) return;

        var matchInfo = null;
        if (rule.type === 'hex') {
            var nc = content.replace(/\s/g, '').toLowerCase();
            var nm = rule.normalizedHex;
            var pos = nc.indexOf(nm);
            if (pos !== -1) matchInfo = { index: pos, length: nm.length };
        } else if (rule.type === 'regex') {
            var m = rule.compiledRegex.exec(content);
            if (m) matchInfo = { index: m.index, length: m[0].length };
        } else if (rule.type === 'keyword') {
            if (rule.compiledRegex.test(content)) {
                var k = content.match(rule.compiledRegex);
                if (k) matchInfo = { index: k.index, length: k[0].length };
            }
        }

        if (matchInfo) {
            // 整行着色（仅首次匹配生效）
            if (!wrapped) {
                var style = 'color:' + (rule.color || 'inherit') + ';' +
                    (rule.background ? 'background:' + rule.background + ';' : '') +
                    (rule.bold ? 'font-weight:700;' : '');
                content = '<span style="border-left:3px solid ' + (rule.color || 'transparent') + ';padding-left:6px;' + style + '">' +
                    content + '</span>';
                wrapped = true;
            }
            // 注解（所有匹配规则都累积）
            if (rule.annotation) {
                annotations.push(
                    '<span class="rule-annotation" style="background:' + (rule.color || '#818cf8') + '20;color:' +
                    (rule.color || '#818cf8') + ';border:1px solid ' + (rule.color || '#818cf8') + '40">' +
                    rule.annotation + '</span>'
                );
            }
        }
    });

    if (annotations.length > 0) {
        content = annotations.join(' ') + ' ' + content;
    }
    return content;
}

// ── 格式化 ──
function formatBytes(bytes) {
    if (!bytes || bytes < 0) return '0B';
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + 'KB';
    return (bytes / 1048576).toFixed(1) + 'MB';
}

function formatDuration(seconds) {
    if (!seconds || seconds <= 0) return '0秒';
    var parts = [];
    var d = Math.floor(seconds / 86400);
    var h = Math.floor((seconds % 86400) / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = seconds % 60;
    if (d > 0) parts.push(d + '天');
    if (h > 0) parts.push(h + '时');
    if (m > 0) parts.push(m + '分');
    if (s > 0 || parts.length === 0) parts.push(Math.floor(s) + '秒');
    return parts.join('');
}

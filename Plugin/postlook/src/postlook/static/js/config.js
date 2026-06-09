/**
 * postlook · 配置管理页面逻辑
 */
var _editorMode = 'main'; // 'main' | 'rules'

document.addEventListener('DOMContentLoaded', function() {
    var configEditor = document.getElementById('configEditor');
    var configStatus = document.getElementById('configStatus');
    var loadConfigBtn = document.getElementById('loadConfigBtn');
    var saveConfigBtn = document.getElementById('saveConfigBtn');
    var loadRulesBtn = document.getElementById('loadRulesBtn');
    var saveRulesBtn = document.getElementById('saveRulesBtn');
    var scanBtn = document.getElementById('scanBtn');
    var scanBase = document.getElementById('scanBase');
    var scanResults = document.getElementById('scanResults');

    // 加载主配置
    loadConfigBtn.addEventListener('click', function() {
        configStatus.textContent = '加载中...';
        configStatus.className = 'config-status';
        fetch('/api/config').then(function(r){return r.json();}).then(function(data){
            configEditor.value = data.content || '';
            configStatus.textContent = '✅ 主配置已加载';
            configStatus.className = 'config-status status-ok';
            _editorMode = 'main';
            updateEditorTabs();
        }).catch(function(err){
            configStatus.textContent = '❌ 加载失败: ' + err.message;
            configStatus.className = 'config-status status-err';
        });
    });

    // 保存主配置
    saveConfigBtn.addEventListener('click', function() {
        var content = configEditor.value.trim();
        if (!content) { configStatus.textContent = '⚠️ 配置内容为空'; configStatus.className = 'config-status status-err'; return; }
        configStatus.textContent = '保存中...';
        configStatus.className = 'config-status';
        fetch('/api/config', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:content})})
            .then(function(r){return r.json();}).then(function(data){
                configStatus.textContent = '✅ ' + (data.message || '保存成功');
                configStatus.className = 'config-status status-ok';
            }).catch(function(err){
                configStatus.textContent = '❌ 保存失败: ' + err.message;
                configStatus.className = 'config-status status-err';
            });
    });

    // 加载规则配置
    if (loadRulesBtn) {
        loadRulesBtn.addEventListener('click', function() {
            configStatus.textContent = '加载中...';
            configStatus.className = 'config-status';
            // 先用 GET /api/rules 获取规则列表，再用 get_rules_toml 获取原始 TOML
            fetch('/api/config').then(function(r){return r.json();}).then(function(data){
                // 尝试直接从 rules.toml 读原文
                return fetch('/api/rules').then(function(r2){return r2.json();});
            }).then(function(data){
                // 重建 TOML 内容
                fetch('/api/rules?raw=1').catch(function(){
                    // 没有 raw 参数，手动构造
                    return {rules: []};
                }).then(function(){
                    // 从 GET /api/config 获取原文的方式不可行，用另一个端点
                    return fetch('/api/rules-toml');
                }).then(function(r){return r.text();}).then(function(toml){
                    configEditor.value = toml;
                    configStatus.textContent = '✅ 规则配置已加载';
                    configStatus.className = 'config-status status-ok';
                    _editorMode = 'rules';
                    updateEditorTabs();
                }).catch(function(){
                    // 兜底
                    configStatus.textContent = '⚠️ 无法加载规则 TOML 原文';
                    configStatus.className = 'config-status status-err';
                });
            }).catch(function(err){
                configStatus.textContent = '❌ 加载失败: ' + err.message;
                configStatus.className = 'config-status status-err';
            });
        });
    }

    // 保存规则配置
    if (saveRulesBtn) {
        saveRulesBtn.addEventListener('click', function() {
            var content = configEditor.value.trim();
            if (!content) { configStatus.textContent = '⚠️ 规则内容为空'; configStatus.className = 'config-status status-err'; return; }
            configStatus.textContent = '保存中...';
            configStatus.className = 'config-status';
            fetch('/api/rules', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:content})})
                .then(function(r){return r.json();}).then(function(data){
                    configStatus.textContent = '✅ ' + (data.message || '规则已保存');
                    configStatus.className = 'config-status status-ok';
                }).catch(function(err){
                    configStatus.textContent = '❌ 保存失败: ' + err.message;
                    configStatus.className = 'config-status status-err';
                });
        });
    }

    // 扫描目录
    scanBtn.addEventListener('click', function() {
        var base = scanBase.value.trim() || '/main/app';
        scanResults.innerHTML = '<div style="font-size:0.75rem;color:var(--text-tertiary);padding:4px">扫描中...</div>';
        fetch('/api/scan-dirs?base=' + encodeURIComponent(base)).then(function(r){return r.json();}).then(function(data){
            if (!data.dirs || data.dirs.length === 0) {
                scanResults.innerHTML = '<div style="font-size:0.75rem;color:var(--text-tertiary);padding:4px">未发现 log/logs 目录</div>';
                return;
            }
            var html = '';
            data.dirs.forEach(function(d) {
                var label = d.path.replace(base, '');
                html += '<label class="sb-label"><input type="checkbox" class="scan-check" value="' + d.path + '"> ' + label + ' <span class="count">' + d.file_count + ' files</span></label>';
            });
            html += '<div style="margin-top:8px;display:flex;gap:6px">' +
                '<button class="btn-secondary" style="font-size:0.75rem;padding:4px 10px" onclick="addScannedDirs()">➕ 添加到配置</button>' +
                '</div>';
            scanResults.innerHTML = html;
        }).catch(function(){
            scanResults.innerHTML = '<div style="font-size:0.75rem;color:var(--danger);padding:4px">扫描失败</div>';
        });
    });

    // 初始加载主配置
    loadConfigBtn.click();
});

function switchEditor(mode) {
    _editorMode = mode;
    updateEditorTabs();
    var el = document.getElementById('configStatus');
    if (mode === 'main') {
        document.getElementById('loadConfigBtn').click();
    } else {
        document.getElementById('loadRulesBtn').click();
    }
}

function updateEditorTabs() {
    var mainTab = document.getElementById('tabMainConfig');
    var rulesTab = document.getElementById('tabRulesConfig');
    if (mainTab && rulesTab) {
        mainTab.className = _editorMode === 'main' ? 'btn-primary' : 'btn-secondary';
        rulesTab.className = _editorMode === 'rules' ? 'btn-primary' : 'btn-secondary';
    }
}

function addScannedDirs() {
    var checks = document.querySelectorAll('.scan-check:checked');
    if (checks.length === 0) return;
    var dirs = [];
    checks.forEach(function(c) { dirs.push(c.value); });
    var editor = document.getElementById('configEditor');
    var current = editor.value;
    // 在 root_dirs 数组中添加新目录
    var rootLine = current.match(/(root_dirs\s*=\s*\[)[^\]]*(\])/);
    if (rootLine) {
        var existing = current.substring(rootLine.index, rootLine.index + rootLine[0].length);
        var newDirs = dirs.filter(function(d) { return existing.indexOf(d) === -1; });
        if (newDirs.length === 0) { document.getElementById('configStatus').textContent = '⚠️ 目录已在白名单中'; return; }
        var insert = newDirs.map(function(d) { return '"' + d + '"'; }).join(', ');
        var before = current.substring(0, rootLine.index + rootLine[1].length);
        var after = current.substring(rootLine.index + rootLine[1].length);
        editor.value = before + (rootLine[1].endsWith('[') ? '' : ', ') + insert + after;
        document.getElementById('configStatus').textContent = '✅ 已添加 ' + newDirs.length + ' 个目录到白名单';
    } else {
        document.getElementById('configStatus').textContent = '⚠️ 无法定位 root_dirs，请手动添加';
    }
}

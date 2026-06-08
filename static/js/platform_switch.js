/**
 * 平台切换页面 — 前端交互
 */
(function () {
    'use strict';

    const DOM = {
        newIp:      document.getElementById('newIp'),
        newPort:    document.getElementById('newPort'),
        sshPass:    document.getElementById('sshPass'),
        hostsInput: document.getElementById('hostsInput'),
        deviceCount: document.getElementById('deviceCount'),
        btnQuery:   document.getElementById('btnQuery'),
        btnExecute: document.getElementById('btnExecute'),
        btnClearLog: document.getElementById('btnClearLog'),
        logArea:    document.getElementById('logArea'),
        resultSection: document.getElementById('resultSection'),
        resultBody: document.getElementById('resultBody'),
        resultSummary: document.getElementById('resultSummary'),
    };

    const STATE = {
        queryResults: [],   // 缓存查询结果
    };

    // ── 工具 ────────────────────────────────────────────────────────

    function getHosts() {
        return DOM.hostsInput.value
            .split('\n')
            .map(s => s.trim())
            .filter(s => s && /^\d+\.\d+\.\d+\.\d+$/.test(s));
    }

    function updateDeviceCount() {
        const hosts = getHosts();
        DOM.deviceCount.textContent = hosts.length + ' 台';
        return hosts;
    }

    function log(msg, cls) {
        const span = document.createElement('div');
        span.className = 'log-' + (cls || 'info');
        span.textContent = '[' + new Date().toLocaleTimeString() + '] ' + msg;
        DOM.logArea.appendChild(span);
        DOM.logArea.scrollTop = DOM.logArea.scrollHeight;
    }

    function clearLog() {
        DOM.logArea.innerHTML = '';
        log('日志已清除', 'muted');
    }

    function setBusy(btn, busy) {
        btn.disabled = busy;
        btn.innerHTML = busy
            ? '<span class="spinner-border spinner-border-sm me-1"></span> 处理中...'
            : btn.dataset.origHtml;
    }

    function showError(msg) {
        log('❌ ' + msg, 'error');
    }

    // ── 渲染结果表格 ────────────────────────────────────────────────

    function renderResults(results) {
        const tbody = DOM.resultBody;
        tbody.innerHTML = '';

        let ok = 0, fail = 0;
        results.forEach(r => {
            const tr = document.createElement('tr');
            const hasData = r.address !== undefined;
            const isOk = r.success !== false;

            if (r.success === true) ok++;
            else if (r.success === false) fail++;

            tr.innerHTML = [
                '<td><code>' + escHtml(r.host) + '</code></td>',
                '<td>' + (hasData ? escHtml(r.address) : '<span class="text-danger">' + escHtml(r.error || 'N/A') + '</span>') + '</td>',
                '<td>' + (r.port || '-') + '</td>',
                '<td>' + (r.success === true ? '<span class="badge badge-ok">✓ 成功</span>'
                    : r.success === false ? '<span class="badge badge-fail">✗ 失败</span>'
                    : '<span class="badge bg-secondary">' + (r.error ? '错误' : '未知') + '</span>') + '</td>',
                '<td><code>' + escHtml(r.device_id || '-') + '</code></td>',
            ].join('');
            tbody.appendChild(tr);
        });

        const total = results.length;
        DOM.resultSummary.textContent = '共 ' + total + ' 台，成功 ' + ok + ' 台' + (fail ? '，失败 ' + fail + ' 台' : '');
        DOM.resultSection.style.display = '';
    }

    function escHtml(s) {
        if (!s) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // ── API 调用 ────────────────────────────────────────────────────

    async function apiPost(url, body) {
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
            body: JSON.stringify(body),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'HTTP ' + resp.status);
        return data;
    }

    // ── 查询 ────────────────────────────────────────────────────────

    async function onQuery() {
        const hosts = updateDeviceCount();
        if (hosts.length === 0) {
            showError('请至少输入一台设备的 IP 地址');
            return;
        }

        setBusy(DOM.btnQuery, true);
        DOM.btnExecute.disabled = true;
        DOM.resultSection.style.display = 'none';
        log('正在查询 ' + hosts.length + ' 台设备的当前配置...', 'info');

        try {
            const data = await apiPost('/api/platform-switch/query', {
                hosts: hosts,
                ssh_pass: DOM.sshPass.value,
            });
            STATE.queryResults = data.results || [];
            renderResults(STATE.queryResults);
            log('查询完成', 'success');
            DOM.btnExecute.disabled = false;
        } catch (e) {
            showError('查询失败: ' + e.message);
        } finally {
            setBusy(DOM.btnQuery, false);
        }
    }

    // ── 执行切换 ────────────────────────────────────────────────────

    async function onExecute() {
        const hosts = getHosts();
        const newIp = DOM.newIp.value.trim();
        const port = parseInt(DOM.newPort.value) || 3002;

        if (hosts.length === 0) {
            showError('设备列表为空');
            return;
        }
        if (!newIp) {
            showError('请填写新的平台 IP');
            return;
        }

        if (!confirm('确认将 ' + hosts.length + ' 台设备的注册平台切换到 ' + newIp + ':' + port + ' 吗？')) {
            return;
        }

        setBusy(DOM.btnExecute, true);
        DOM.btnQuery.disabled = true;
        log('开始切换 ' + hosts.length + ' 台设备...', 'info');

        try {
            const data = await apiPost('/api/platform-switch/execute', {
                hosts: hosts,
                new_ip: newIp,
                port: port,
                ssh_pass: DOM.sshPass.value,
            });
            const results = data.results || [];
            renderResults(results);

            let ok = 0, fail = 0;
            results.forEach(r => {
                if (r.success) {
                    ok++;
                    log(r.host + '  ✓  ' + (r.old ? r.old.address + ' → ' : '') + newIp, 'success');
                } else {
                    fail++;
                    log(r.host + '  ✗  ' + (r.error || '失败'), 'error');
                }
            });
            log('切换完成: 成功 ' + ok + ' 台' + (fail ? '，失败 ' + fail + ' 台' : ''), ok > 0 ? 'success' : 'error');
        } catch (e) {
            showError('切换失败: ' + e.message);
        } finally {
            setBusy(DOM.btnExecute, false);
            DOM.btnQuery.disabled = false;
        }
    }

    // ── 事件绑定 ────────────────────────────────────────────────────

    DOM.hostsInput.addEventListener('input', updateDeviceCount);
    DOM.btnQuery.addEventListener('click', onQuery);
    DOM.btnExecute.addEventListener('click', onExecute);
    DOM.btnClearLog.addEventListener('click', clearLog);

    // 初始化
    updateDeviceCount();
    log('就绪，输入设备 IP 和目标平台后点击"查询当前配置"', 'muted');

})();

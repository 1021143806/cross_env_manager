/**
 * postlook · 报文调试交互逻辑 (v0.4.0)
 * TCP Client: 连接→发送→接收→断开（一连接一断）
 * 仿 SSCOM 多字符串面板设计
 */

document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    // ═══════════════════════════════════════════════
    //  状态管理
    // ═══════════════════════════════════════════════
    var _sending = false;           // 防抖锁
    var _sendTimer = null;         // 防抖定时器
    var SEND_DEBOUNCE = 500;       // 500ms 防抖
    var _msgData = null;           // 报文数据缓存
    var _debugConfig = null;       // 调试配置缓存

    // ═══════════════════════════════════════════════
    //  DOM 引用
    // ═══════════════════════════════════════════════
    var $ = function (id) { return document.getElementById(id); };

    var elHost = $('connHost');
    var elPort = $('connPort');
    var elTestBtn = $('btnTestConn');
    var elTestResult = $('testResult');
    var elOptLower = $('optLowercase');
    var elOptUpper = $('optUppercase');
    var elOptShowHex = $('optShowHex');
    var elOptTimestamp = $('optTimestamp');
    var elManualHex = $('manualHex');
    var elManualSend = $('btnManualSend');
    var elMsgPanel = $('msgPanel');
    var elLogContainer = $('logContainer');
    var elLogHexToggle = $('logHexToggle');
    var elClearLog = $('btnClearLog');
    var elToast = $('toast');
    var elTomlModal = $('tomlModal');
    var elTomlEditor = $('tomlEditor');
    var elTomlTitle = $('tomlModalTitle');

    // ═══════════════════════════════════════════════
    //  Toast 通知
    // ═══════════════════════════════════════════════
    var _toastTimer = null;
    function showToast(msg, type) {
        type = type || 'info';
        elToast.textContent = msg;
        elToast.className = 'toast ' + type + ' show';
        if (_toastTimer) clearTimeout(_toastTimer);
        _toastTimer = setTimeout(function () {
            elToast.classList.remove('show');
        }, 2500);
    }

    // ═══════════════════════════════════════════════
    //  发送日志
    // ═══════════════════════════════════════════════
    function formatTime() {
        var d = new Date();
        var h = String(d.getHours()).padStart(2, '0');
        var m = String(d.getMinutes()).padStart(2, '0');
        var s = String(d.getSeconds()).padStart(2, '0');
        var ms = String(d.getMilliseconds()).padStart(3, '0');
        return h + ':' + m + ':' + s + '.' + ms;
    }

    function addLog(dir, label, hexStr, elapsedMs, textStr) {
        var showTs = elOptTimestamp.checked;
        var showHex = elLogHexToggle.checked;
        var entry = document.createElement('div');
        entry.className = 'log-entry ' + (dir === 'send' ? 'sent' : dir === 'recv' ? 'recv' : 'error');

        var parts = [];
        if (showTs) parts.push('<span class="ts">[' + formatTime() + ']</span>');

        if (dir === 'send') {
            parts.push('<span class="dir">→</span> ' + escapeHtml(label || '发送'));
        } else if (dir === 'recv') {
            parts.push('<span class="dir">←</span> ');
            if (elapsedMs !== undefined) parts.push('<span class="ts">' + elapsedMs + 'ms</span> ');
        } else {
            parts.push('<span class="dir">✗</span> ');
        }

        if (hexStr && showHex) {
            parts.push('<br><span style="padding-left:20px;opacity:0.8;word-break:break-all;">' + escapeHtml(hexStr) + '</span>');
        }
        // 显示可读文本版本（接收时如果存在）
        if (dir === 'recv' && textStr) {
            parts.push('<br><span style="padding-left:20px;color:var(--accent);font-weight:500;">' + escapeHtml(textStr) + '</span>');
        }

        entry.innerHTML = parts.join('');
        elLogContainer.appendChild(entry);
        elLogContainer.scrollTop = elLogContainer.scrollHeight;
    }

    function clearLog() {
        elLogContainer.innerHTML = '';
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // ═══════════════════════════════════════════════
    //  加载连接配置
    // ═══════════════════════════════════════════════
    function loadDebugConfig() {
        fetch('/api/debug/config')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                _debugConfig = data.config;
                var conn = _debugConfig.connection;
                elHost.value = conn.host || '';
                elPort.value = conn.port || '';

                var send = _debugConfig.send;
                elOptLower.checked = send.auto_lowercase !== false;
                elOptUpper.checked = send.auto_uppercase === true;

                var display = _debugConfig.display;
                elOptShowHex.checked = display.show_hex !== false;
                elOptTimestamp.checked = display.show_timestamp !== false;
            })
            .catch(function (e) {
                console.error('加载调试配置失败:', e);
            });
    }

    function saveDebugConfig() {
        var toml = [
            '[connection]',
            'host = "' + elHost.value.trim() + '"',
            'port = ' + (parseInt(elPort.value) || 8899),
            'timeout = 3.0',
            'recv_timeout = 1.0',
            'recv_buffer = 4096',
            '',
            '[send]',
            'auto_lowercase = ' + (elOptLower.checked ? 'true' : 'false'),
            'auto_uppercase = ' + (elOptUpper.checked ? 'true' : 'false'),
            'add_crlf_ascii = true',
            '',
            '[display]',
            'show_hex = ' + (elOptShowHex.checked ? 'true' : 'false'),
            'show_timestamp = ' + (elOptTimestamp.checked ? 'true' : 'false'),
        ].join('\n');

        return fetch('/api/debug/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: toml }),
        }).then(function (r) { return r.json(); });
    }

    // 选项变化时自动保存
    [elOptLower, elOptUpper, elOptShowHex, elOptTimestamp].forEach(function (el) {
        el.addEventListener('change', function () {
            saveDebugConfig().catch(function () {});
        });
    });
    elHost.addEventListener('blur', function () { saveDebugConfig().catch(function () {}); });
    elPort.addEventListener('blur', function () { saveDebugConfig().catch(function () {}); });

    // 大小写互斥
    elOptLower.addEventListener('change', function () {
        if (elOptLower.checked) elOptUpper.checked = false;
    });
    elOptUpper.addEventListener('change', function () {
        if (elOptUpper.checked) elOptLower.checked = false;
    });

    // ═══════════════════════════════════════════════
    //  测试连接（Ping + 端口）
    // ═══════════════════════════════════════════════
    function testConnection() {
        var host = elHost.value.trim();
        var port = parseInt(elPort.value) || 8899;
        if (!host) { showToast('请输入目标主机', 'error'); return; }

        elTestBtn.disabled = true;
        elTestBtn.innerHTML = '<span class="spinner"></span> 检测中...';
        elTestResult.classList.remove('show');

        fetch('/api/debug/test-connection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host: host, port: port }),
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var html = '';
            // Ping
            var p = data.ping;
            if (p.reachable) {
                var lat = p.latency_ms !== null ? p.latency_ms + 'ms' : '可达';
                html += '<div class="item"><span class="dot ok"></span> Ping <b style="color:var(--success)">✓ 可达</b> ' + lat + '</div>';
            } else {
                html += '<div class="item"><span class="dot fail"></span> Ping <b style="color:var(--danger)">✗ ' + escapeHtml(p.error || '不可达') + '</b></div>';
            }
            // Port
            var pt = data.port;
            if (pt.open) {
                html += '<div class="item"><span class="dot ok"></span> 端口 <b style="color:var(--success)">✓ 开放</b> ' + pt.elapsed_ms + 'ms</div>';
            } else {
                var cls = p.reachable ? 'fail' : 'skip';
                html += '<div class="item"><span class="dot ' + cls + '"></span> 端口 <b style="color:var(--warning)">' + escapeHtml(pt.error || '检测失败') + '</b></div>';
            }
            elTestResult.innerHTML = html;
            elTestResult.classList.add('show');

            // 保存配置
            saveDebugConfig().catch(function () {});
        })
        .catch(function (e) {
            elTestResult.innerHTML = '<div class="item"><span class="dot fail"></span> <b style="color:var(--danger)">检测异常: ' + escapeHtml(e.message) + '</b></div>';
            elTestResult.classList.add('show');
        })
        .finally(function () {
            elTestBtn.disabled = false;
            elTestBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> 测试连接';
        });
    }

    elTestBtn.addEventListener('click', testConnection);

    // ═══════════════════════════════════════════════
    //  发送报文（核心）
    // ═══════════════════════════════════════════════
    function sendHex(hexStr, label) {
        if (_sending) {
            showToast('操作过快，请稍后重试', 'error');
            return;
        }

        label = label || hexStr.substring(0, 30);
        _sending = true;

        // 标记发送中的按钮
        var allSendBtns = document.querySelectorAll('.btn-send');
        allSendBtns.forEach(function (b) { b.classList.add('sending'); });

        addLog('send', label, hexStr);

        fetch('/api/debug/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ hex: hexStr }),
        })
        .then(function (r) {
            if (!r.ok) {
                return r.json().then(function (err) {
                    throw new Error(err.detail || 'HTTP ' + r.status);
                });
            }
            return r.json();
        })
        .then(function (data) {
            if (data.received_hex) {
                addLog('recv', '', data.received_hex, data.total_ms, data.received_text);
            } else {
                addLog('recv', '(无响应)', null, data.total_ms);
            }
            showToast('发送成功 · ' + data.sent_bytes + 'B · ' + data.total_ms + 'ms', 'success');
        })
        .catch(function (e) {
            addLog('error', '错误: ' + e.message);
            showToast('发送失败: ' + e.message, 'error');
        })
        .finally(function () {
            // 防抖恢复
            if (_sendTimer) clearTimeout(_sendTimer);
            _sendTimer = setTimeout(function () {
                _sending = false;
                allSendBtns.forEach(function (b) { b.classList.remove('sending'); });
            }, SEND_DEBOUNCE);
        });
    }

    // 手动发送
    elManualSend.addEventListener('click', function () {
        var hex = elManualHex.value.trim();
        if (!hex) { showToast('请输入 HEX 报文', 'error'); return; }
        sendHex(hex, '手动发送');
    });

    // 回车发送
    elManualHex.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            elManualSend.click();
        }
    });

    // ═══════════════════════════════════════════════
    //  加载报文数据
    // ═══════════════════════════════════════════════
    function loadMessages() {
        elMsgPanel.innerHTML = '<div class="glass-card" style="padding:16px;text-align:center;color:var(--text-tertiary)"><span class="spinner"></span> 加载报文中...</div>';

        fetch('/api/debug/messages')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                _msgData = data;
                renderMessages(data.groups || []);
            })
            .catch(function (e) {
                elMsgPanel.innerHTML = '<div class="glass-card" style="padding:16px;text-align:center;color:var(--danger)">加载失败: ' + escapeHtml(e.message) + '</div>';
            });
    }

    function renderMessages(groups) {
        if (!groups || groups.length === 0) {
            elMsgPanel.innerHTML = '<div class="glass-card" style="padding:24px;text-align:center;color:var(--text-tertiary)"><p style="margin-bottom:8px">暂无报文数据</p><p style="font-size:0.75rem">点击左侧「TOML 源文件」编辑 data/messages.toml 添加报文</p></div>';
            return;
        }

        var html = '';
        groups.forEach(function (g, gi) {
            var msgCount = (g.message && g.message.length) || 0;
            html += '<div class="msg-group">';
            html += '<div class="msg-group-header" onclick="this.parentElement.classList.toggle(\'collapsed\')">';
            html += '<span class="arrow">▼</span>';
            html += '<span>' + escapeHtml(g.name || '分组 ' + (gi + 1)) + '</span>';
            html += '<span style="font-size:0.65rem;color:var(--text-tertiary);margin-left:auto">' + msgCount + ' 条</span>';
            html += '</div>';
            if (g.desc) {
                html += '<div class="msg-group-desc">' + escapeHtml(g.desc) + '</div>';
            }

            if (g.message && g.message.length > 0) {
                html += '<div class="msg-group-body">';
                g.message.forEach(function (m) {
                    var hex = m.hex || '';
                    var type = m.type || 'hex';
                    var annotation = m.annotation || '';
                    var safeName = escapeHtml(m.name || hex.substring(0, 20));
                    var safeHex = escapeHtml(hex.length > 40 ? hex.substring(0, 40) + '...' : hex);

                    html += '<div class="msg-row">';
                    html += '<span class="msg-name" title="' + escapeHtml(annotation) + '">' + safeName + '</span>';
                    html += '<span class="msg-hex" title="' + escapeHtml(hex) + '">' + safeHex + '</span>';
                    html += '<button class="btn-send" onclick="window._sendMsg(\'' + escapeHtmlAttr(hex) + '\', \'' + escapeHtmlAttr(m.name) + '\')">发送</button>';
                    html += '</div>';
                });
                html += '</div>';
            }
            html += '</div>';
        });

        elMsgPanel.innerHTML = html;
    }

    // 暴露给 onclick 的全局发送函数
    window._sendMsg = function (hex, name) {
        sendHex(hex, name || '报文发送');
    };

    function escapeHtmlAttr(str) {
        if (!str) return '';
        return String(str).replace(/&/g, '&amp;').replace(/'/g, '&#39;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // ═══════════════════════════════════════════════
    //  TOML 编辑模态框
    // ═══════════════════════════════════════════════
    function openTomlEditor(title, loadUrl, saveUrl, onSaved) {
        elTomlTitle.textContent = title;

        fetch(loadUrl)
            .then(function (r) { return r.text(); })
            .then(function (text) {
                elTomlEditor.value = text;
                elTomlModal.classList.add('show');
                setTimeout(function () { elTomlEditor.focus(); }, 100);
            })
            .catch(function (e) {
                showToast('加载失败: ' + e.message, 'error');
            });

        // 保存按钮
        var saveHandler = function () {
            var content = elTomlEditor.value;
            fetch(saveUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: content }),
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === 'ok') {
                    showToast('保存成功 · 已热更新', 'success');
                    elTomlModal.classList.remove('show');
                    if (onSaved) onSaved();
                    loadMessages();  // 刷新报文列表
                } else {
                    showToast('保存失败: ' + (data.detail || data.message || '未知错误'), 'error');
                }
            })
            .catch(function (e) {
                showToast('保存失败: ' + e.message, 'error');
            });
        };

        // 清理旧的监听器
        var newSaveBtn = $('tomlModalSave');
        var newCancelBtn = $('tomlModalCancel');
        var newCloseBtn = $('tomlModalClose');
        newSaveBtn.replaceWith(newSaveBtn.cloneNode(true));
        newCancelBtn.replaceWith(newCancelBtn.cloneNode(true));
        newCloseBtn.replaceWith(newCloseBtn.cloneNode(true));

        $('tomlModalSave').addEventListener('click', saveHandler);
        $('tomlModalCancel').addEventListener('click', function () { elTomlModal.classList.remove('show'); });
        $('tomlModalClose').addEventListener('click', function () { elTomlModal.classList.remove('show'); });
    }

    $('btnTomlEdit').addEventListener('click', function () {
        openTomlEditor('编辑 messages.toml', '/api/debug/messages-toml', '/api/debug/messages', function () {
            // 热更新后刷新
        });
    });

    $('btnVisualEdit').addEventListener('click', function () {
        showToast('可视化编辑功能开发中，请使用 TOML 源文件编辑', 'info');
    });

    // 点击模态框外关闭
    elTomlModal.addEventListener('click', function (e) {
        if (e.target === elTomlModal) elTomlModal.classList.remove('show');
    });

    // 清空日志
    elClearLog.addEventListener('click', clearLog);

    // hex 显示切换
    elLogHexToggle.addEventListener('change', function () {
        // 日志切换 hex 显示时给出提示
    });

    // ═══════════════════════════════════════════════
    //  键盘快捷键
    // ═══════════════════════════════════════════════
    document.addEventListener('keydown', function (e) {
        // Esc 关闭模态框
        if (e.key === 'Escape' && elTomlModal.classList.contains('show')) {
            elTomlModal.classList.remove('show');
        }
    });

    // ═══════════════════════════════════════════════
    //  主题适配（复用 common.js）
    // ═══════════════════════════════════════════════
    // common.js 已处理主题切换，调试页只需跟随

    // ═══════════════════════════════════════════════
    //  初始化
    // ═══════════════════════════════════════════════
    loadDebugConfig();
    loadMessages();
});

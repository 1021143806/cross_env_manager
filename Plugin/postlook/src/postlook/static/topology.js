/**
 * topology.js — postlook 服务拓扑图
 * 基于 Cytoscape.js，展示 server 10.76.2.4 的服务-日志关系
 * v0.2.0
 */

(function () {
'use strict';

// ============================================================
//  节点数据定义
// ============================================================

const CATEGORIES = {
    apps: {
        id: 'cat-apps', label: '应用系统', color: '#0abde3',
        desc: '25 个 Java/Spring Boot 微服务',
    },
    planner: {
        id: 'cat-planner', label: '路径规划', color: '#e94560',
        desc: '7 个 C++ 算法进程',
    },
    middleware: {
        id: 'cat-middleware', label: '中间件', color: '#f39c12',
        desc: 'Nacos / Filebeat',
    },
    system: {
        id: 'cat-system', label: '系统日志', color: '#10ac84',
        desc: '内核 / 安全 / 定时任务',
    },
    database: {
        id: 'cat-database', label: '数据库', color: '#9b59b6',
        desc: 'MariaDB 8.4.8',
    },
};

const SERVICES = [
    // 应用系统 (25)
    { id: 'gateway',    label: 'gateway',    cat: 'apps', logDir: '/main/app/gateway/logs',      logFile: 'GATEWAY.log',     size: 48.8, desc: 'API 网关 / 鉴权 / 路由' },
    { id: 'bms',        label: 'BMS',        cat: 'apps', logDir: '/main/app/bms/logs',          logFile: 'BMS.log',         size: 96.9, desc: '业务管理 / 订单 / 地图' },
    { id: 'rdms',       label: 'RDMS',       cat: 'apps', logDir: '/main/app/rdms/logs',         logFile: 'RDMS.log',        size: 118,  desc: '资源调度 (最大日志)' },
    { id: 'pms',        label: 'PMS',        cat: 'apps', logDir: '/main/app/pms/logs',          logFile: 'PMS.log',         size: 43.2, desc: '任务管理' },
    { id: 'sps',        label: 'SPS',        cat: 'apps', logDir: '/main/app/sps/logs',          logFile: 'SPS.log',         size: 30.0, desc: '路径服务' },
    { id: 'tps',        label: 'TPS',        cat: 'apps', logDir: '/main/app/tps/logs',          logFile: 'TPS.log',         size: 27.4, desc: '任务处理' },
    { id: 'gws',        label: 'GWS',        cat: 'apps', logDir: '/main/app/gws/logs',          logFile: 'GWS.log',         size: 31.3, desc: '网关 WebSocket 服务' },
    { id: 'ics',        label: 'ICS',        cat: 'apps', logDir: '/main/app/ics/logs',          logFile: 'ICS.log',         size: 19.3, desc: '交叉控制' },
    { id: 'revent',     label: 'REVENT',     cat: 'apps', logDir: '/main/app/revent/logs',       logFile: 'REVENT.log',      size: 12.8, desc: '事件上报' },
    { id: 'wdcs',       label: 'WDCS',       cat: 'apps', logDir: '/main/app/wdcs/logs',         logFile: 'WDCS.log',        size: 11.0, desc: '仓库数据采集' },
    { id: 'call',       label: 'CALL',       cat: 'apps', logDir: '/main/app/call/logs',         logFile: 'CALL.log',        size: 7.2,  desc: '呼叫系统' },
    { id: 'hoist',      label: 'HOIST',      cat: 'apps', logDir: '/main/app/hoist/logs',        logFile: 'HOIST.log',       size: 5.4,  desc: '提升机控制' },
    { id: 'fms',        label: 'FMS',        cat: 'apps', logDir: '/main/app/fms/logs',          logFile: 'FMS.log',         size: 5.0,  desc: '车队管理' },
    { id: 'ilcs',       label: 'ILCS',       cat: 'apps', logDir: '/main/app/ilcs/logs',         logFile: 'ILCS.log',        size: 4.7,  desc: '交叉控制 (IL)' },
    { id: 'roc',        label: 'ROC',        cat: 'apps', logDir: '/main/app/roc/logs',          logFile: 'roc.log',         size: 4.9,  desc: '远程操作中心' },
    { id: 'cms',        label: 'CMS',        cat: 'apps', logDir: '/main/app/cms/logs',          logFile: 'CMS.log',         size: 3.7,  desc: '配置管理' },
    { id: 'camera',     label: 'CAMERA',     cat: 'apps', logDir: '/main/app/camera/logs',       logFile: 'CAMERA.log',      size: 2.8,  desc: '相机服务' },
    { id: 'pssproxy',   label: 'PSS-PROXY',  cat: 'apps', logDir: '/main/app/pss-proxy/logs',    logFile: 'PSS-PROXY.log',   size: 2.2,  desc: '代理服务' },
    { id: 'commonscene', label: 'commonScene',cat: 'apps', logDir: '/main/app/commonScene/logs',  logFile: 'COMMONSCENE.log', size: 2.0,  desc: '通用场景' },
    { id: 'accessCtrl', label: 'accessControl',cat:'apps', logDir: '/main/app/accessControl/logs',logFile: '',              size: 0,    desc: '门禁 (C++)' },
    { id: 'light',      label: 'LIGHT',      cat: 'apps', logDir: '/main/app/light/logs',        logFile: 'LIGHT.log',       size: 0.2,  desc: '灯光控制' },
    { id: 'wkb',        label: 'WKB',        cat: 'apps', logDir: '/main/app/wkb/logs',          logFile: 'wkb.log',         size: 0.3,  desc: '货架 / 库位' },
    { id: 'wca',        label: 'WCA',        cat: 'apps', logDir: '/main/app/wca/logs',          logFile: 'WCA.log',         size: 0.2,  desc: '称重' },
    { id: 'wfs',        label: 'WFS',        cat: 'apps', logDir: '/main/app/wfs/logs',          logFile: 'WFS.log',         size: 0.3,  desc: '仓库文件服务' },
    { id: 'hrcamera',   label: 'HR-CAMERA',  cat: 'apps', logDir: '/main/app/hr-camera/logs',    logFile: 'hr-camera.log',   size: 0.2,  desc: '高拍相机' },

    // 路径规划 (7)
    { id: 'rtpsa',      label: 'rtpsa-all',  cat: 'planner', logDir: '/main/app/rtpsa-2,3,4,5,6/logs', logFile: 'rtps.log', size: 0, desc: '任务分配 (C++)' },
    { id: 'rtpsp2',     label: 'rtpsp-2',    cat: 'planner', logDir: '/main/app/rtpsp-2/logs',   logFile: 'rtps.log', size: 0, desc: '路径规划 2号机' },
    { id: 'rtpsp3',     label: 'rtpsp-3',    cat: 'planner', logDir: '/main/app/rtpsp-3/logs',   logFile: 'rtps.log', size: 0, desc: '路径规划 3号机' },
    { id: 'rtpsp4',     label: 'rtpsp-4',    cat: 'planner', logDir: '/main/app/rtpsp-4/logs',   logFile: 'rtps.log', size: 0, desc: '路径规划 4号机' },
    { id: 'rtpsp5',     label: 'rtpsp-5',    cat: 'planner', logDir: '/main/app/rtpsp-5/logs',   logFile: 'rtps.log', size: 0, desc: '路径规划 5号机' },
    { id: 'rtpsp6',     label: 'rtpsp-6',    cat: 'planner', logDir: '/main/app/rtpsp-6/logs',   logFile: 'rtps.log', size: 0, desc: '路径规划 6号机' },
    { id: 'gpl',        label: 'gpl-all',    cat: 'planner', logDir: '/main/app/gpl-2,3,4,5,6/logs', logFile: 'gpl.log', size: 0, desc: '通用规划 (C++)' },

    // 中间件 (2)
    { id: 'nacos',      label: 'Nacos',      cat: 'middleware', logDir: '/main/server/nacos/logs', logFile: 'nacos.log', size: 14.2, desc: '服务注册 / 配置中心' },
    { id: 'filebeat',   label: 'Filebeat',   cat: 'middleware', logDir: '/main/server/filebeat/logs', logFile: '', size: 0, desc: '日志采集' },

    // 系统日志 (5)
    { id: 'messages',   label: 'messages',   cat: 'system', logDir: '/var/log', logFile: 'messages',  size: 4.0, desc: '系统消息 (内核 / OOM / sshd)' },
    { id: 'secure',     label: 'secure',     cat: 'system', logDir: '/var/log', logFile: 'secure',    size: 5.1, desc: '安全认证 (SSH 登录)' },
    { id: 'cron',       label: 'cron',       cat: 'system', logDir: '/var/log', logFile: 'cron',      size: 1.3, desc: '定时任务执行记录' },
    { id: 'sa08',       label: 'sa08',       cat: 'system', logDir: '/var/log/sa', logFile: 'sa08',  size: 0.6, desc: 'sysstat 性能数据 (二进制)' },
    { id: 'dnf',        label: 'dnf',        cat: 'system', logDir: '/var/log', logFile: 'dnf.log',   size: 0.1, desc: '包管理器日志' },

    // 数据库 (1)
    { id: 'mariadb',    label: 'MariaDB',    cat: 'database', logDir: '/main/server/mysql', logFile: 'mysql_error.log', size: 0.3, desc: 'MariaDB 8.4.8 错误日志' },
];

// ============================================================
//  构建 Cytoscape 节点/边
// ============================================================

function buildElements() {
    var nodes = [];
    var edges = [];

    // 中心节点
    nodes.push({
        data: { id: 'server', label: '10.76.2.4\n服务器', type: 'server', weight: 100 },
        classes: 'server',
    });

    // 分类节点
    for (var key in CATEGORIES) {
        var cat = CATEGORIES[key];
        nodes.push({
            data: { id: cat.id, label: cat.label, type: 'category', weight: 60 },
            classes: 'category ' + key,
        });
        edges.push({
            data: { source: 'server', target: cat.id, weight: 2 },
        });
    }

    // 服务节点
    for (var i = 0; i < SERVICES.length; i++) {
        var svc = SERVICES[i];
        var cat = CATEGORIES[svc.cat];
        var nodeSize = Math.max(20, Math.min(50, (svc.size || 0.1) * 0.35 + 18));
        nodes.push({
            data: {
                id: svc.id,
                label: svc.label,
                type: 'service',
                category: svc.cat,
                desc: svc.desc,
                logDir: svc.logDir,
                logFile: svc.logFile,
                sizeMB: svc.size,
                weight: nodeSize,
            },
            classes: 'service ' + svc.cat,
        });
        edges.push({
            data: { source: cat.id, target: svc.id, weight: 1 },
        });
    }

    return { nodes: nodes, edges: edges };
}

// ============================================================
//  创建 Cytoscape 实例
// ============================================================

var cy;
var selectedNode = null;
var timeoutRefresh = null;

function initCytoscape() {
    var elements = buildElements();

    cy = cytoscape({
        container: document.getElementById('cy'),
        elements: elements,
        style: [
            // 服务器节点
            {
                selector: '.server',
                style: {
                    'background-color': '#16213e',
                    'label': 'data(label)',
                    'color': '#e0e0e0',
                    'font-size': '13px',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'width': 120,
                    'height': 120,
                    'border-width': 3,
                    'border-color': '#0abde3',
                    'text-wrap': 'wrap',
                    'text-max-width': '80px',
                },
            },
            // 分类节点
            {
                selector: '.category',
                style: {
                    'background-color': '#0f3460',
                    'label': 'data(label)',
                    'color': '#ccc',
                    'font-size': '13px',
                    'font-weight': 'bold',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'width': 80,
                    'height': 80,
                    'border-width': 2,
                    'text-wrap': 'wrap',
                },
            },
            {
                selector: '.apps',
                style: { 'border-color': '#0abde3' },
            },
            {
                selector: '.planner',
                style: { 'border-color': '#e94560' },
            },
            {
                selector: '.middleware',
                style: { 'border-color': '#f39c12' },
            },
            {
                selector: '.system',
                style: { 'border-color': '#10ac84' },
            },
            {
                selector: '.database',
                style: { 'border-color': '#9b59b6' },
            },
            // 服务节点
            {
                selector: '.service',
                style: {
                    'background-color': '#1a1a3e',
                    'label': 'data(label)',
                    'color': '#d0d0d0',
                    'font-size': '11px',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'width': 'data(weight)',
                    'height': 'data(weight)',
                    'border-width': 1.5,
                    'text-wrap': 'wrap',
                    'text-max-width': '60px',
                },
            },
            // 边
            {
                selector: 'edge',
                style: {
                    'width': 1,
                    'line-color': '#2a2a4a',
                    'curve-style': 'bezier',
                    'opacity': 0.6,
                },
            },
            // 选中
            {
                selector: '.service:selected',
                style: {
                    'border-width': 3,
                    'border-color': '#fff',
                    'background-color': '#2a2a5e',
                },
            },
            // hover
            {
                selector: '.service:active',
                style: {
                    'overlay-opacity': 0.15,
                },
            },
        ],
        layout: {
            name: 'concentric',
            concentric: function (node) {
                var type = node.data('type');
                if (type === 'server') return 0;
                if (type === 'category') return 1;
                return 2 + Math.random() * 0.5;
            },
            minNodeSpacing: 18,
            padding: 40,
            animate: false,
            avoidOverlap: true,
        },
        wheelSensitivity: 0.3,
        userZoomingEnabled: true,
        userPanningEnabled: true,
        minZoom: 0.2,
        maxZoom: 3,
    });

    // ---- 事件绑定 ----

    // 点击服务节点 → 打开侧边面板
    cy.on('tap', '.service', function (evt) {
        var node = evt.target;
        selectService(node);
    });

    // 点击分类节点 → 高亮该分类
    cy.on('tap', '.category', function (evt) {
        var node = evt.target;
        var catId = node.data('id');
        // 高亮属于该分类的所有子节点
        cy.elements().removeClass('highlight');
        cy.nodes('[category="' + 
            Object.keys(CATEGORIES).find(function (k) { return CATEGORIES[k].id === catId; }) + 
            '"]').addClass('highlight');
    });

    // 点击空白取消选中
    cy.on('tap', function (evt) {
        if (evt.target === cy) {
            cy.elements().removeClass('highlight');
        }
    });

    // tooltip on hover
    var tooltipDiv = document.createElement('div');
    tooltipDiv.className = 'tooltip-div';
    document.body.appendChild(tooltipDiv);

    cy.on('mouseover', '.service', function (evt) {
        var node = evt.target;
        var desc = node.data('desc') || '';
        var size = node.data('sizeMB') || 0;
        var logFile = node.data('logFile') || '';
        var txt = node.data('label');
        if (desc) txt += '\n' + desc;
        if (size > 0) txt += '\n日志: ' + size.toFixed(1) + 'MB';
        if (logFile) txt += '\n文件: ' + logFile;
        tooltipDiv.innerHTML = txt.replace(/\n/g, '<br>');
        tooltipDiv.style.display = 'block';
        tooltipDiv.style.left = (evt.renderedPosition.x + 15) + 'px';
        tooltipDiv.style.top = (evt.renderedPosition.y - 15) + 'px';
    });

    cy.on('mouseout', '.service', function () {
        tooltipDiv.style.display = 'none';
    });

    cy.on('mousemove', '.service', function (evt) {
        tooltipDiv.style.left = (evt.renderedPosition.x + 15) + 'px';
        tooltipDiv.style.top = (evt.renderedPosition.y - 15) + 'px';
    });

    // 加载完成
    document.getElementById('statusInfo').textContent = '34 个日志源就绪';
}

// ============================================================
//  侧边面板逻辑
// ============================================================

function selectService(node) {
    selectedNode = node;
    var panel = document.getElementById('sidePanel');
    var content = document.getElementById('panelContent');
    panel.classList.add('open');

    var label = node.data('label');
    var logDir = node.data('logDir');
    var logFile = node.data('logFile');
    var desc = node.data('desc') || '';
    var sizeMB = node.data('sizeMB') || 0;

    content.innerHTML = 
        '<div class="panel-header">' +
            '<h3>📄 <span class="service-name">' + escapeHtml(label) + '</span></h3>' +
            '<button class="panel-close" onclick="closePanel()">✕</button>' +
        '</div>' +
        '<div class="panel-section">' +
            '<h4>' + escapeHtml(desc) + '</h4>' +
            '<div style="font-size:12px;color:var(--text-secondary)">' +
                (sizeMB ? '日志大小: <b>' + sizeMB.toFixed(1) + ' MB</b>' : '') +
                '&nbsp;&nbsp;路径: <code>' + escapeHtml(logDir) + '</code>' +
            '</div>' +
        '</div>' +
        '<div class="panel-section">' +
            '<h4>🔍 日志文件</h4>' +
            '<div class="file-list" id="fileList">' +
                '<div class="loading">⏳ 加载文件列表...</div>' +
            '</div>' +
        '</div>' +
        '<div class="panel-section">' +
            '<h4>📋 最新日志预览</h4>' +
            '<div class="log-preview" id="logPreview">' +
                '<div class="loading">⏳ 加载日志...</div>' +
            '</div>' +
        '</div>' +
        '<div style="display:flex;gap:8px;margin-top:args:8px">' +
            (logFile ? '<button class="btn btn-primary" onclick="downloadLog(\'' + logDir + '/' + logFile + '\')">⬇ 下载最新日志</button>' : '') +
            '<button class="btn" style="background:var(--card-bg);color:var(--text);border:1px solid var(--border)" onclick="refreshLogs()">🔄 刷新</button>' +
        '</div>';

    // 加载文件列表
    loadFileList(logDir);

    // 如果有主日志文件，加载预览
    if (logFile) {
        loadLogPreview(logDir, logFile);
    }
}

function closePanel() {
    document.getElementById('sidePanel').classList.remove('open');
    selectedNode = null;
}

function loadFileList(dir) {
    fetch('/api/files')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var fileList = document.getElementById('fileList');
            if (!fileList) return;
            var html = '';
            for (var i = 0; i < data.directories.length; i++) {
                var d = data.directories[i];
                if (d.path === dir || d.path.indexOf(dir) === 0) {
                    for (var j = 0; j < d.files.length; j++) {
                        var f = d.files[j];
                        if (j >= 15 && html.split('<div class="file-item">').length > 5) {
                            html += '<div style="font-size:11px;color:var(--text-secondary);padding:4px">... 共 ' + d.files.length + ' 个文件，仅显示前15个</div>';
                            break;
                        }
                        html += '<div class="file-item" onclick="viewFile(\'' + f.path + '\')" title="点击查看">' +
                            '<div class="file-name">' + escapeHtml(f.name) + '</div>' +
                            '<div style="display:flex;gap:4px;align-items:center">' +
                                '<span class="file-size">' + formatSize(f.size) + '</span>' +
                                '<span class="file-action" title="下载" onclick="event.stopPropagation();downloadLog(\'' + f.path + '\')">⬇</span>' +
                                '<span class="file-action download" title="查看" onclick="event.stopPropagation();viewFile(\'' + f.path + '\')">👁</span>' +
                            '</div>' +
                        '</div>';
                    }
                    break;
                }
            }
            if (!html) html = '<div style="font-size:12px;color:var(--text-secondary);padding:8px">暂无文件</div>';
            fileList.innerHTML = html;
        })
        .catch(function (err) {
            var el = document.getElementById('fileList');
            if (el) el.innerHTML = '<div style="color:var(--accent);font-size:12px">加载失败: ' + err.message + '</div>';
        });
}

function loadLogPreview(dir, file) {
    fetch('/api/logs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            folder: dir,
            pattern: file,
            tail: true,
            line_start: 1,
            line_end: 80,
            recent_files: 1,
        }),
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var preview = document.getElementById('logPreview');
            if (!preview) return;
            if (!data.results || data.results.length === 0) {
                preview.innerHTML = '<div style="color:var(--text-secondary);padding:10px">暂无日志内容</div>';
                return;
            }
            var html = '';
            for (var i = 0; i < data.results.length; i++) {
                var line = data.results[i].content;
                var cls = 'log-line';
                if (/ERROR|error|Error/.test(line)) cls += ' error';
                else if (/WARN|warn/.test(line)) cls += ' warn';
                html += '<div class="' + cls + '">' + escapeHtml(line) + '</div>';
            }
            preview.innerHTML = html;
        })
        .catch(function (err) {
            var el = document.getElementById('logPreview');
            if (el) el.innerHTML = '<div style="color:var(--accent);font-size:12px">加载失败: ' + err.message + '</div>';
        });
}

// ============================================================
//  操作方法
// ============================================================

function viewFile(path) {
    // 直接访问日志查询面板
    window.location.href = '/?file=' + encodeURIComponent(path);
}

function downloadLog(path) {
    window.open('/api/download?path=' + encodeURIComponent(path), '_blank');
}

function refreshLogs() {
    if (selectedNode) {
        selectService(selectedNode);
    }
}

// ============================================================
//  工具函数
// ============================================================

function escapeHtml(s) {
    if (!s) return '';
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    var units = ['B', 'KB', 'MB', 'GB'];
    var i = Math.floor(Math.log(bytes) / Math.log(1024));
    if (i >= units.length) i = units.length - 1;
    return (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1) + ' ' + units[i];
}

// ============================================================
//  启动
// ============================================================

window.closePanel = closePanel;
window.downloadLog = downloadLog;
window.viewFile = viewFile;
window.refreshLogs = refreshLogs;

document.addEventListener('DOMContentLoaded', function () {
    initCytoscape();
});

})();

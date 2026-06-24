/**
 * postlook · 拓扑图 — 多视图切换 (v0.10.0)
 * 
 * 视图: 放射图 | 树形图 | 同心圆
 * 数据源: /api/topology-config → {nodes, edges}
 * 状态色: 🟢 running / ⬜ idle / ⚫ missing
 */

var cy = null;
var topoInited = false;
var TOPO_DATA = null;
var TOPO_LOADING = false;

// ── 视图注册表 ──
var LAYOUTS = {};
var currentLayout = (function () {
    try { return localStorage.getItem('topo-layout') || 'horizontal'; }
    catch (e) { return 'horizontal'; }
})();

document.addEventListener('DOMContentLoaded', function () {

    // ── 加载拓扑数据 ──
    window.loadTopoData = function (callback) {
        if (TOPO_DATA) return callback(TOPO_DATA);
        if (TOPO_LOADING) { setTimeout(function () { loadTopoData(callback); }, 200); return; }
        TOPO_LOADING = true;
        fetch('/api/topology-config').then(function (r) { return r.json(); }).then(function (data) {
            TOPO_DATA = { nodes: data.nodes || [], edges: data.edges || [] };
            callback(TOPO_DATA);
        }).catch(function () {
            // 回退：显示一个空根节点
            TOPO_DATA = {
                nodes: [
                    { data: { id: 'root', label: '/', type: 'root', level: 0 } }
                ],
                edges: []
            };
            callback(TOPO_DATA);
        });
    };

    // ── 初始化拓扑 ──
    function initTopology() {
        if (topoInited) { if (cy) { cy.resize(); cy.fit(undefined, 30); } return; }
        topoInited = true;
        var container = document.getElementById('cy');
        if (!container) return;
        var statusEl = document.getElementById('topoStatus');
        if (statusEl) statusEl.textContent = '扫描文件树...';
        loadTopoData(function (data) {
            _initTopoWithData(container, data);
        });
    }

    // ── 渲染拓扑图 ──
    function _initTopoWithData(container, data) {
        // 为每个节点添加 CSS class: type + 状态
        var elements = [];
        (data.nodes || []).forEach(function (n) {
            var d = n.data || n;
            var classes = [d.type || 'service'];
            if (d.running) classes.push('running');
            if (d.size_mb <= 0 && d.type === 'service') classes.push('empty');

            // 对数映射日志大小 → 节点尺寸（18~50px）
            if (d.type === 'service') {
                d.weight = d.size_mb > 0
                    ? Math.round(Math.max(18, Math.min(50, 18 + Math.log2(d.size_mb + 0.05) * 8)))
                    : 22;
            }

            elements.push({ data: d, classes: classes.join(' ') });
        });
        (data.edges || []).forEach(function (e) {
            elements.push({ data: e.data || e });
        });

        cy = cytoscape({
            container: container,
            elements: elements,
            style: [
                // 根节点 — 圆角矩形，醒目
                {
                    selector: '.root',
                    style: {
                        'shape': 'round-rectangle', 'width': 90, 'height': 40,
                        'background-color': '#818cf8', 'background-opacity': 0.25,
                        'border-width': 2.5, 'border-color': '#818cf8',
                        'label': 'data(label)', 'color': '#e8e8f8',
                        'font-size': '13px', 'font-weight': 'bold',
                        'text-valign': 'center', 'text-halign': 'center',
                        'text-wrap': 'wrap', 'text-max-width': '80px'
                    }
                },
                // 目录分支节点 — 胶囊形
                {
                    selector: '.branch',
                    style: {
                        'shape': 'ellipse', 'width': 65, 'height': 32,
                        'background-color': '#475569', 'background-opacity': 0.2,
                        'border-width': 1.5, 'border-color': '#64748b',
                        'label': 'data(label)', 'color': '#a0aec0',
                        'font-size': '10.5px', 'font-weight': '600',
                        'text-valign': 'center', 'text-halign': 'center',
                        'text-wrap': 'wrap', 'text-max-width': '60px'
                    }
                },
                // 服务节点 — 大小按日志量自适应
                {
                    selector: '.service',
                    style: {
                        'shape': 'ellipse',
                        'width': 'data(weight)',
                        'height': 'data(weight)',
                        'background-color': '#334155', 'background-opacity': 0.55,
                        'border-width': 1.5, 'border-color': '#475569',
                        'label': 'data(label)', 'color': '#c0c0d0',
                        'font-size': '9px', 'text-valign': 'center', 'text-halign': 'center',
                        'text-wrap': 'wrap', 'text-max-width': '55px'
                    }
                },
                // 运行中的服务 🟢
                {
                    selector: '.service.running',
                    style: {
                        'background-color': '#22c55e', 'background-opacity': 0.22,
                        'border-color': '#22c55e', 'border-width': 2,
                        'shadow-color': '#22c55e', 'shadow-opacity': 0.25,
                        'shadow-blur': 8, 'shadow-offset-x': 0, 'shadow-offset-y': 0
                    }
                },
                // 空项目（无日志/不存在）⚫
                {
                    selector: '.service.empty',
                    style: {
                        'background-color': '#1e293b', 'background-opacity': 0.3,
                        'border-color': '#334155', 'border-style': 'dashed',
                        'border-width': 1
                    }
                },
                // 选中态
                {
                    selector: '.service:selected',
                    style: { 'border-width': 3, 'border-color': '#f8fafc' }
                },
                // 边 — 直线，思维导图风格
                {
                    selector: 'edge',
                    style: {
                        'width': 1.5,
                        'line-color': 'rgba(129,140,248,0.3)',
                        'curve-style': 'haystack',
                        'opacity': 0.5
                    }
                }
            ],
            // 不传 layout，手动控制定位
            wheelSensitivity: 0.3,
            userZoomingEnabled: true,
            userPanningEnabled: true,
            minZoom: 0.08,
            maxZoom: 3,
            autoungrabify: false,
            autounselectify: false
        });

        // 状态栏
        var svcCount = cy.nodes('.service').length;
        var branchCount = cy.nodes('.branch').length;
        var runningCount = cy.nodes('.service.running').length;
        document.getElementById('topoStatus').textContent =
            branchCount + ' 目录 · ' + svcCount + ' 服务' + (runningCount ? ' · ' + runningCount + ' 运行中' : '');

        // 使用当前选择的布局
        applyLayout(cy);
        initBreathing(cy);

        // ── 点击事件 ──
        cy.on('tap', '.service', function (evt) { showTopoDetail(evt.target); });
        cy.on('tap', '.branch', function (evt) { toggleBranch(evt.target); });
        cy.on('tap', function (evt) { if (evt.target === cy) closeTopoDetail(); });

        // ── 侧栏图层 ──
        renderLayerPanel(cy);
        renderViewButtons();
        // ── 侧栏图例 ──
        var legendDiv = document.querySelector('.sb-legend');
        if (legendDiv) {
            legendDiv.innerHTML =
                '<div class="sb-legend-item"><span class="sb-legend-dot" style="background:#22c55e;box-shadow:0 0 6px #22c55e"></span>运行中（supervisor）</div>' +
                '<div class="sb-legend-item"><span class="sb-legend-dot" style="background:#475569"></span>服务节点</div>' +
                '<div class="sb-legend-item"><span class="sb-legend-dot" style="background:#475569;border:1px dashed #64748b"></span>无数据</div>';
        }
    }

    // ════════════════════════════════════════════════════════════
    //  布局引擎：dagre（mermaid 同款，自动间距 + 永不重叠）
    // ════════════════════════════════════════════════════════════

    LAYOUTS = {
        horizontal: { name: '横向', icon: '⇢', rankDir: 'LR', rankSep: 110, nodeSep: 38 },
        vertical:   { name: '纵向', icon: '⇣', rankDir: 'TB', rankSep: 90,  nodeSep: 34 },
        compact:    { name: '紧凑', icon: '⊞', rankDir: 'LR', rankSep: 55,  nodeSep: 24, ranker: 'tight-tree' }
    };

    function applyLayout(cy) {
        var cfg = LAYOUTS[currentLayout] || LAYOUTS['horizontal'];
        cy.layout({
            name: 'dagre',
            rankDir: cfg.rankDir,
            rankSep: cfg.rankSep,
            nodeSep: cfg.nodeSep,
            edgeSep: 15,
            ranker: cfg.ranker || 'network-simplex',
            animate: true,
            animationDuration: 500,
            fit: true,
            padding: 50
        }).run();
    }

    window.switchLayout = function (name) {
        if (!cy || !LAYOUTS[name]) return;
        currentLayout = name;
        try { localStorage.setItem('topo-layout', name); } catch (e) {}
        applyLayout(cy);
        renderViewButtons();
    };

    function renderViewButtons() {
        var container = document.getElementById('viewSwitcher');
        if (!container) return;
        var html = '';
        for (var key in LAYOUTS) {
            var active = key === currentLayout ? ' active' : '';
            html += '<button class="view-btn' + active + '" onclick="switchLayout(\'' + key + '\')" title="' + LAYOUTS[key].name + '">' +
                LAYOUTS[key].icon + ' ' + LAYOUTS[key].name + '</button>';
        }
        container.innerHTML = html;
    }

    // ── 侧栏图层：目录分支列表 ──

    // ── 侧栏图层：目录分支列表 ──
    function renderLayerPanel(cy) {
        var layersDiv = document.getElementById('topoLayers');
        if (!layersDiv) return;
        var branches = cy.nodes('.branch');
        if (branches.length === 0) { layersDiv.innerHTML = ''; return; }
        var h = '<div class="sb-labels">';
        branches.forEach(function (b) {
            var id = b.id();
            var label = escapeHtml(b.data('label') || id);
            var childCount = b.connectedEdges().filter(function (e) { return e.source().id() === id; }).length;
            h += '<label class="sb-label"><input type="checkbox" checked data-branch="' + id + '" onchange="toggleBranch(\'' + id + '\',this.checked)">' +
                '<span class="sb-legend-dot" style="background:#475569"></span> ' + label +
                '<span class="count">' + childCount + '</span></label>';
        });
        h += '</div>';
        layersDiv.innerHTML = h;
    }

    // ── 切换分支可见性 ──
    window.toggleBranch = function (branchId, show) {
        if (!cy) return;
        var branch = cy.getElementById(branchId);
        if (!branch.length) return;
        if (typeof show === 'undefined') show = branch.style('display') === 'none';
        branch.style('display', show ? 'element' : 'none');
        // 隐藏/显示该分支下的所有服务节点和边
        branch.connectedEdges().forEach(function (e) {
            var child = e.target();
            if (child.id() === branchId) child = e.source();
            child.style('display', show ? 'element' : 'none');
            e.style('display', show ? 'element' : 'none');
        });
        // 重排布局
        applyLayout(cy);
    };

    // ── 呼吸灯：运行中的服务节点柔光脉冲 ──
    function initBreathing(cy) {
        cy.nodes('.service.running').forEach(function (node) {
            var expanding = true;
            function breathe() {
                node.animate({
                    style: {
                        'shadow-opacity': expanding ? 0.5 : 0.12,
                        'shadow-blur': expanding ? 16 : 6,
                        'border-width': expanding ? 3 : 2
                    }
                }, {
                    duration: 2200,
                    easing: 'ease-in-out',
                    complete: function () {
                        expanding = !expanding;
                        breathe();
                    }
                });
            }
            // 随机起始相位，避免所有节点同步闪烁
            setTimeout(breathe, Math.random() * 1500);
        });
    }

    // ── 连线脉冲动画（已弃用，保留备用）──
    function initEdgePulses(cy) {
        cy.edges().forEach(function (edge) {
            var src = edge.source(), tgt = edge.target();
            var color = '#818cf8';
            if (tgt.hasClass('running')) color = '#22c55e';
            else if (tgt.hasClass('empty')) color = '#475569';

            var pulse = cy.add({
                group: 'nodes',
                data: { id: 'pulse-' + edge.id() },
                classes: 'pulse-dot',
                position: src.position()
            });
            pulse.style('background-color', color);
            pulse.style('underlay-color', color);

            function firePulse() {
                pulse.position(src.position());
                pulse.style('opacity', 1);
                pulse.animate({
                    position: { x: tgt.position('x'), y: tgt.position('y') },
                    style: { 'opacity': 0.2 }
                }, {
                    duration: 2200,
                    easing: 'ease-in-out',
                    complete: function () {
                        pulse.style('opacity', 1);
                        firePulse();
                    }
                });
            }
            setTimeout(firePulse, Math.random() * 1200);
        });
    }

    // ── 搜索过滤 ──
    window.filterTopoNodes = function (query) {
        if (!cy) return;
        var q = query.toLowerCase().trim();
        cy.nodes('.service').forEach(function (n) {
            var label = (n.data('label') || '').toLowerCase();
            var logDir = (n.data('log_dir') || '').toLowerCase();
            var match = q === '' || label.indexOf(q) >= 0 || logDir.indexOf(q) >= 0;
            n.style('display', match ? 'element' : 'none');
        });
        // 高亮匹配的分支
        cy.nodes('.branch').forEach(function (b) {
            var label = (b.data('label') || '').toLowerCase();
            if (q === '') { b.style('border-color', '#64748b'); return; }
            var hasMatch = false;
            b.connectedEdges().forEach(function (e) {
                var child = e.target().id() === b.id() ? e.source() : e.target();
                if (child.hasClass('service') && child.style('display') !== 'none') hasMatch = true;
            });
            b.style('border-color', hasMatch || label.indexOf(q) >= 0 ? '#818cf8' : '#64748b');
        });
    };

    // ── 显示详情面板（点击服务节点）──
    window.showTopoDetail = function (node) {
        try {
            var el = document.getElementById('topoDetail');
            var nameEl = document.getElementById('topoDetailName');
            var body = document.getElementById('topoDetailBody');
            if (!el || !nameEl || !body) return;
            el.style.display = 'flex';

            var label = node.data('label') || node.id();
            var logDir = node.data('log_dir') || '';
            var logFile = node.data('log_file') || '';
            var sizeMB = node.data('size_mb') || 0;
            var running = node.data('running') || false;
            var status = running ? '<span style="color:#22c55e;font-weight:600">● 运行中</span>' : '<span style="color:#64748b">○ 未运行</span>';

            nameEl.innerHTML = label + ' <span style="font-size:0.7rem;font-weight:400">' + status + '</span>';

            var html = '<div style="margin-bottom:8px;color:var(--text-tertiary);font-size:0.75rem">路径: ' + (logDir || '—') + ' | 主日志: ' + (logFile || '—') + ' | ' + (sizeMB ? sizeMB.toFixed(1) + ' MB' : '') + '</div>';
            html += '<div style="margin-bottom:4px;font-weight:600;font-size:0.8rem">日志文件</div>';
            html += '<div id="topoFileList" style="margin-bottom:10px">加载中...</div>';
            html += '<div style="font-weight:600;font-size:0.8rem">最新预览</div>';
            html += '<div class="log-preview" id="topoLogPreview">加载中...</div>';
            html += '<div style="margin-top:10px;display:flex;gap:6px">';
            if (logFile && logDir) html += '<button class="file-actions" style="padding:4px 12px" onclick="window.open(\'/api/download?path=' + encodeURIComponent(logDir + '/' + logFile) + '\')">⬇ 下载</button>';
            html += '<button class="file-actions" style="padding:4px 12px" onclick="closeTopoDetail()">关闭</button></div>';
            body.innerHTML = html;

            // 加载文件列表
            if (logDir) {
                fetch('/api/files').then(function (r) { return r.json(); }).then(function (data) {
                    var fl = document.getElementById('topoFileList');
                    if (!fl) return;
                    var items = '';
                    if (data.directories) {
                        for (var i = 0; i < data.directories.length; i++) {
                            var d = data.directories[i];
                            if (d.path === logDir || d.path.indexOf(logDir + '/') === 0) {
                                for (var j = 0; j < Math.min(d.files.length, 10); j++) {
                                    var f = d.files[j];
                                    items += '<div class="file-row"><span class="file-name" title="' + f.path + '">' + f.name + '</span><span class="file-size">' + formatBytes(f.size) + '</span><div class="file-actions"><button onclick="window.open(\'/api/download?path=' + encodeURIComponent(f.path) + '\')">⬇</button><button onclick="viewTopoLog(\'' + encodeURIComponent(f.path) + '\')">👁</button></div></div>';
                                }
                                break;
                            }
                        }
                    }
                    fl.innerHTML = items || '暂无文件';
                }).catch(function () { var fl = document.getElementById('topoFileList'); if (fl) fl.innerHTML = '加载失败'; });

                // 加载日志预览
                if (logFile) {
                    fetch('/api/logs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ folder: logDir, pattern: logFile, tail: true, line_start: 1, line_end: 60, recent_files: 1 }) })
                        .then(function (r) { return r.json(); }).then(function (data) {
                            var lp = document.getElementById('topoLogPreview');
                            if (!lp) return;
                            var lines = '';
                            if (data.results) for (var i = 0; i < data.results.length; i++) { var c = data.results[i].content; lines += '<div style="font-size:0.68rem;white-space:nowrap;line-height:1.3">' + escapeHtml(c) + '</div>'; }
                            lp.innerHTML = lines || '暂无日志';
                        }).catch(function () { var lp = document.getElementById('topoLogPreview'); if (lp) lp.innerHTML = '加载失败'; });
                }
            }
        } catch (e) { console.error('topoDetail error:', e); }
    };

    window.closeTopoDetail = function () { var el = document.getElementById('topoDetail'); if (el) el.style.display = 'none'; };
    window.viewTopoLog = function (path) { window.open('logs.html?folder=' + encodeURIComponent(decodeURIComponent(path))); };

    // ════════════════════════════════════════════════════════════
    //  自动发现服务 (v0.7.0) — 保留
    // ════════════════════════════════════════════════════════════

    var DISCOVER_DATA = null;

    window.openDiscoverModal = function () {
        var overlay = document.getElementById('discoverOverlay');
        var body = document.getElementById('discoverBody');
        var selectAllBtn = document.getElementById('selectAllBtn');
        var mergeBtn = document.getElementById('mergeBtn');
        if (!overlay || !body) return;
        overlay.style.display = 'flex';
        body.innerHTML = '<div class="discover-loading">正在扫描 supervisor + 目录...</div>';
        selectAllBtn.style.display = 'none';
        mergeBtn.style.display = 'none';
        fetch('/api/topology/discover').then(function (r) { return r.json(); }).then(function (data) {
            DISCOVER_DATA = data;
            renderDiscoverList(data);
        }).catch(function (err) {
            body.innerHTML = '<div class="discover-error">扫描失败: ' + (err.message || '网络错误') + '</div>';
        });
    };

    window.closeDiscoverModal = function () {
        var overlay = document.getElementById('discoverOverlay');
        if (overlay) overlay.style.display = 'none';
        DISCOVER_DATA = null;
    };

    function renderDiscoverList(data) {
        var body = document.getElementById('discoverBody');
        var selectAllBtn = document.getElementById('selectAllBtn');
        var mergeBtn = document.getElementById('mergeBtn');
        if (!body) return;
        var cs = data.candidates || [];
        var cats = data.categories || [];
        if (cs.length === 0) {
            body.innerHTML = '<div class="discover-empty">未发现新的服务节点<br><small>确保 supervisor 和 /main/app 目录可访问</small></div>';
            selectAllBtn.style.display = 'none';
            mergeBtn.style.display = 'none';
            return;
        }
        var newCount = cs.filter(function (c) { return c.is_new; }).length;
        selectAllBtn.style.display = newCount > 0 ? '' : 'none';
        mergeBtn.style.display = newCount > 0 ? '' : 'none';

        var html = '<div class="discover-summary">发现 <b>' + cs.length + '</b> 个候选服务，其中 <b style="color:var(--accent)">' + newCount + '</b> 个为新服务</div>';
        html += '<div class="discover-list">';
        for (var i = 0; i < cs.length; i++) {
            var c = cs[i], isNew = c.is_new;
            var rowClass = isNew ? 'discover-row new' : 'discover-row existing';
            var checked = isNew ? ' checked' : '';
            var disabled = isNew ? '' : ' disabled';
            var badge = isNew ? '<span class="discover-badge new">新</span>' : '<span class="discover-badge exist">已有</span>';
            html += '<div class="' + rowClass + '">';
            html += '<label class="discover-check"><input type="checkbox" data-id="' + c.id + '"' + checked + disabled + ' onchange="onCandidateToggle()"></label>';
            html += '<div class="discover-info">';
            html += '<div class="discover-name">' + escapeHtml(c.name) + badge + '</div>';
            html += '<div class="discover-meta">';
            html += '<select class="discover-cat" data-id="' + c.id + '" onchange="onCatChange(this)">';
            for (var j = 0; j < cats.length; j++) {
                var sel = cats[j].id === c.category ? ' selected' : '';
                html += '<option value="' + cats[j].id + '"' + sel + '>' + cats[j].label + '</option>';
            }
            html += '</select>';
            html += '<span class="discover-path">' + escapeHtml(c.log_dir || '—') + '</span>';
            if (c.log_file) html += '<span class="discover-file">📄 ' + escapeHtml(c.log_file) + '</span>';
            if (c.size_mb) html += '<span class="discover-size">' + c.size_mb.toFixed(1) + ' MB</span>';
            html += '<span class="discover-src">来源: ' + c.source + '</span>';
            html += '</div></div></div>';
        }
        html += '</div>';
        body.innerHTML = html;
    }

    window.selectAllNew = function () {
        if (!DISCOVER_DATA) return;
        var boxes = document.querySelectorAll('.discover-row.new input[type=checkbox]');
        var allChecked = true;
        for (var i = 0; i < boxes.length; i++) { if (!boxes[i].checked) { allChecked = false; break; } }
        for (var i = 0; i < boxes.length; i++) boxes[i].checked = !allChecked;
        onCandidateToggle();
    };

    window.onCandidateToggle = function () {
        var mergeBtn = document.getElementById('mergeBtn');
        if (!mergeBtn) return;
        var checked = document.querySelectorAll('.discover-row input[type=checkbox]:checked');
        mergeBtn.textContent = '合并选中 (' + checked.length + ')';
        mergeBtn.style.opacity = checked.length === 0 ? '0.5' : '1';
    };

    window.onCatChange = function (sel) {
        if (!DISCOVER_DATA) return;
        var id = sel.getAttribute('data-id');
        for (var i = 0; i < DISCOVER_DATA.candidates.length; i++) {
            if (DISCOVER_DATA.candidates[i].id === id) { DISCOVER_DATA.candidates[i].category = sel.value; break; }
        }
    };

    window.mergeSelected = function () {
        if (!DISCOVER_DATA) return;
        var boxes = document.querySelectorAll('.discover-row input[type=checkbox]:checked');
        if (boxes.length === 0) return;
        var selected = [];
        for (var i = 0; i < boxes.length; i++) {
            var id = boxes[i].getAttribute('data-id');
            for (var j = 0; j < DISCOVER_DATA.candidates.length; j++) {
                var c = DISCOVER_DATA.candidates[j];
                if (c.id === id) { selected.push({ id: c.id, name: c.name, category: c.category, log_dir: c.log_dir, log_file: c.log_file, size_mb: c.size_mb, source: c.source }); break; }
            }
        }
        var mergeBtn = document.getElementById('mergeBtn');
        if (mergeBtn) { mergeBtn.textContent = '合并中...'; mergeBtn.disabled = true; }
        fetch('/api/topology/merge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ selected: selected }) })
            .then(function (r) { return r.json(); }).then(function (result) {
                if (result.status === 'ok') {
                    closeDiscoverModal();
                    TOPO_DATA = null;
                    if (cy) { cy.destroy(); cy = null; }
                    topoInited = false;
                    initTopology();
                    alert('已添加 ' + result.added + ' 个节点' + (result.skipped ? '，跳过 ' + result.skipped + ' 个' : ''));
                } else { alert('合并失败: ' + (result.message || '未知错误')); }
            }).catch(function (err) { alert('合并失败: ' + (err.message || '网络错误')); })
            .finally(function () { if (mergeBtn) { mergeBtn.textContent = '合并选中'; mergeBtn.disabled = false; } });
    };

    // 启动
    initTopology();
});

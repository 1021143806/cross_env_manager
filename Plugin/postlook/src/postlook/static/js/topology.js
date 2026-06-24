/**
 * postlook · 知识图谱 (v0.14.0)
 * 
 * 布局: D3 forceSimulation（弹簧引力 + 磁铁斥力 + 水面漂浮）
 * 数据源: /api/topology-kg → {nodes, edges}
 */

var cy = null;
var topoInited = false;
var TOPO_DATA = null;
var TOPO_LOADING = false;

document.addEventListener('DOMContentLoaded', function () {

    // ── 加载拓扑数据 ──
    window.loadTopoData = function (callback) {
        if (TOPO_DATA) return callback(TOPO_DATA);
        if (TOPO_LOADING) { setTimeout(function () { loadTopoData(callback); }, 200); return; }
        TOPO_LOADING = true;
        var url = '/api/topology-kg';
        fetch(url).then(function (r) { return r.json(); }).then(function (data) {
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
        // 为每个节点添加 CSS class
        var elements = [];
        (data.nodes || []).forEach(function (n) {
            var d = n.data || n;
            var classes = [d.type || 'service'];
            if (d.running) classes.push('running');
            if (d.type === 'error_query') classes.push('error');

            // 对数映射大小
            if (d.type === 'service') {
                d.weight = d.size_mb > 0
                    ? Math.round(Math.max(18, Math.min(50, 18 + Math.log2(d.size_mb + 0.05) * 8)))
                    : 22;
                if (d.deprecated) classes.push('deprecated');
            } else if (d.type === 'logfile') {
                d.weight = Math.round(Math.max(14, Math.min(32, 14 + Math.log2((d.size_mb || 0.1) + 0.05) * 6)));
            }

            elements.push({ data: d, classes: classes.join(' ') });
        });
        (data.edges || []).forEach(function (e) {
            var d = e.data || e;
            if (d.relation) {
                elements.push({ data: d, classes: d.relation });
            } else {
                elements.push({ data: d });
            }
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
                // 边 — haystack 基础
                {
                    selector: 'edge',
                    style: {
                        'width': 1.5,
                        'line-color': 'rgba(129,140,248,0.3)',
                        'curve-style': 'haystack',
                        'opacity': 0.5
                    }
                },
                // 知识图谱边颜色
                {
                    selector: '.produces',
                    style: { 'line-color': 'rgba(148,163,184,0.35)', 'width': 1.2 }
                },
                {
                    selector: '.has_query',
                    style: { 'line-color': 'rgba(251,191,36,0.4)', 'width': 2, 'line-style': 'dashed' }
                },
                {
                    selector: '.runs_on',
                    style: { 'line-color': 'rgba(129,140,248,0.3)', 'width': 1 }
                },
                {
                    selector: '.belongs_to',
                    style: { 'line-color': 'rgba(129,140,248,0.2)', 'width': 1, 'line-style': 'dashed' }
                },
                // 服务器节点 — 大圆紫
                {
                    selector: '.server',
                    style: {
                        'shape': 'ellipse', 'width': 85, 'height': 85,
                        'background-color': '#818cf8', 'background-opacity': 0.18,
                        'border-width': 2.5, 'border-color': '#818cf8',
                        'label': 'data(label)', 'color': '#e0e0f0',
                        'font-size': '12px', 'font-weight': 'bold',
                        'text-valign': 'center', 'text-halign': 'center',
                        'text-wrap': 'wrap', 'text-max-width': '70px'
                    }
                },
                // 日志文件节点 — 小圆蓝灰
                {
                    selector: '.logfile',
                    style: {
                        'shape': 'ellipse',
                        'width': 'data(weight)', 'height': 'data(weight)',
                        'background-color': '#64748b', 'background-opacity': 0.35,
                        'border-width': 1.5, 'border-color': '#94a3b8',
                        'label': 'data(label)', 'color': '#b0b8c8',
                        'font-size': '8px', 'text-valign': 'center', 'text-halign': 'center',
                        'text-wrap': 'wrap', 'text-max-width': '50px'
                    }
                },
                // 普通查询节点 — 中圆黄
                {
                    selector: '.query',
                    style: {
                        'shape': 'ellipse', 'width': 30, 'height': 30,
                        'background-color': '#fbbf24', 'background-opacity': 0.22,
                        'border-width': 1.5, 'border-color': '#fbbf24',
                        'label': 'data(label)', 'color': '#fcd34d',
                        'font-size': '8px', 'text-valign': 'center', 'text-halign': 'center',
                        'text-wrap': 'wrap', 'text-max-width': '70px'
                    }
                },
                // 错误查询节点 — 中圆红
                {
                    selector: '.error_query',
                    style: {
                        'shape': 'ellipse', 'width': 34, 'height': 34,
                        'background-color': '#ef4444', 'background-opacity': 0.25,
                        'border-width': 2, 'border-color': '#ef4444',
                        'label': 'data(label)', 'color': '#fca5a5',
                        'font-size': '8px', 'text-valign': 'center', 'text-halign': 'center',
                        'text-wrap': 'wrap', 'text-max-width': '70px',
                        'shadow-color': '#ef4444', 'shadow-opacity': 0.2,
                        'shadow-blur': 6
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

        // 启动 D3 力仿真
        _startKgSimulation(cy);
        initBreathing(cy);

        // ── 点击事件 ──
        cy.on('tap', 'node', function (evt) { showKgPanel(evt.target); });
        cy.on('tap', function (evt) { if (evt.target === cy) closeKgPanel(); });

        // ── D3 拖拽：固定节点 + 加热仿真 → 水面涟漪 ──
        cy.on('grab', 'node', function (evt) {
            if (!kgSimulation) return;
            var n = evt.target;
            var dn = kgSimulation.nodes().find(function (d) { return d.id === n.id(); });
            if (dn) { dn.fx = dn.x; dn.fy = dn.y; }
        });
        cy.on('drag', 'node', function (evt) {
            if (!kgSimulation) return;
            var n = evt.target;
            var dn = kgSimulation.nodes().find(function (d) { return d.id === n.id(); });
            if (dn) {
                dn.fx = n.position('x');
                dn.fy = n.position('y');
                kgSimulation.alpha(0.25).restart();
            }
        });
        cy.on('free', 'node', function (evt) {
            if (!kgSimulation) return;
            var n = evt.target;
            var dn = kgSimulation.nodes().find(function (d) { return d.id === n.id(); });
            if (dn) {
                dn.fx = null; dn.fy = null;
                dn.vx = 0; dn.vy = 0;
                kgSimulation.alpha(0.12).restart();
            }
        });

        // ── 侧栏 ──
        renderLayerPanel(cy);
        renderViewButtons();

        // 默认隐藏日志文件节点（减少杂乱）
        if (!kgShowLogs) {
            cy.nodes('.logfile').style('display', 'none');
            cy.edges('.produces').style('display', 'none');
        }

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
    //  D3 力仿真引擎（KG 视图专用）
    // ════════════════════════════════════════════════════════════

    var kgSimulation = null;

    function _startKgSimulation(cy) {
        stopKgSimulation();

        // 从 Cytoscape 提取节点和边数据
        var nodes = [];
        cy.nodes().forEach(function (n) {
            if (n.style('display') === 'none') return;
            var p = n.position();
            nodes.push({ id: n.id(), x: p.x || 0, y: p.y || 0 });
        });
        var edges = [];
        cy.edges().forEach(function (e) {
            if (e.style('display') === 'none') return;
            edges.push({ source: e.source().id(), target: e.target().id() });
        });

        kgSimulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(edges).id(function (d) { return d.id; })
                .distance(70).strength(0.25))
            .force('charge', d3.forceManyBody().strength(-200))
            .force('center', d3.forceCenter())
            .alphaDecay(0.012)        // 慢衰减 → 水面漂浮停缓
            .velocityDecay(0.45)      // 摩擦力
            .on('tick', function () {
                if (!cy || cy.destroyed()) return;
                var positions = {};
                nodes.forEach(function (d) { positions[d.id] = { x: d.x, y: d.y }; });
                cy.nodes().positions(function (n) {
                    return positions[n.id()] || n.position();
                });
            });

        kgSimulation.alpha(0.4);    // 初始能量
        cy.fit(undefined, 60);
    }

    function stopKgSimulation() {
        if (kgSimulation) { kgSimulation.stop(); kgSimulation = null; }
    }

    // ════════════════════════════════════════════════════════════
    //  侧栏按钮渲染
    // ════════════════════════════════════════════════════════════

    function renderViewButtons() {
        var tidyBtn = document.getElementById('tidyBtn');
        var logBtn = document.getElementById('toggleLogBtn');
        if (tidyBtn) tidyBtn.style.display = '';
        if (logBtn) { logBtn.style.display = ''; logBtn.innerHTML = kgShowLogs ? '📄 日志文件: 关' : '📄 日志文件: 开'; }
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
        _startKgSimulation(cy);
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

            var html = '';
            // 跳转日志页按钮
            if (logDir) {
                html += '<a class="topo-jump-link" href="logs.html?folder=' + encodeURIComponent(logDir) + '" target="_blank" title="在新标签页搜索此目录日志">🔍 搜索此目录日志</a>';
            }
            html += '<div style="margin-bottom:8px;color:var(--text-tertiary);font-size:0.75rem">路径: ' + (logDir || '—') + ' | 主日志: ' + (logFile || '—') + ' | ' + (sizeMB ? sizeMB.toFixed(1) + ' MB' : '') + '</div>';
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
    //  交错入场动画 + 自动互斥
    // ════════════════════════════════════════════════════════════

    function _staggeredEntrance(cy) {
        try {
            // BFS 计算深度
            var depths = {};
            var roots = cy.nodes().filter(function (n) {
                return n.incomers('node').length === 0;
            });
            var q = [];
            roots.forEach(function (r) { q.push({ id: r.id(), d: 0 }); });
            while (q.length) {
                var cur = q.shift();
                if (cur.id in depths) continue;
                depths[cur.id] = cur.d;
                var node = cy.getElementById(cur.id);
                if (node.length) {
                    node.outgoers('node').forEach(function (child) {
                        q.push({ id: child.id(), d: cur.d + 1 });
                    });
                }
            }

            cy.nodes().forEach(function (n) {
                var d = depths[n.id()] || 0;
                // 确保节点可见，再渐入
                n.style('opacity', 0.01);
                n.animate({
                    style: { 'opacity': 1 }
                }, {
                    duration: 400,
                    delay: d * 80,
                    easing: 'ease-out'
                });
            });
        } catch (e) {
            // 动画失败时强制所有节点可见
            cy.nodes().style('opacity', 1);
        }
    }

    window.tidyUpKG = function () {
        if (!cy) return;
        stopKgSimulation();
        _startKgSimulation(cy);
    };

    var kgShowLogs = false;  // KG 默认隐藏日志文件节点

    window.toggleLogNodes = function () {
        if (!cy) return;
        kgShowLogs = !kgShowLogs;
        var btn = document.getElementById('toggleLogBtn');
        if (btn) btn.innerHTML = kgShowLogs ? '📄 日志文件: 关' : '📄 日志文件: 开';
        cy.nodes('.logfile').forEach(function (n) {
            n.style('display', kgShowLogs ? 'element' : 'none');
        });
        cy.edges('.produces').forEach(function (e) {
            e.style('display', kgShowLogs ? 'element' : 'none');
        });
        // 隐藏后重排
        if (!kgShowLogs) {
            cy.layout({
                name: 'cose',
                nodeRepulsion: 10000, nodeOverlap: 20,
                idealEdgeLength: 100, gravity: 0.5,
                numIter: 1500, animate: true,
                animationDuration: 400, fit: true, padding: 60
            }).run();
        }
    };

    window.showKgPanel = function (node) {
        if (!cy) return;
        var el = document.getElementById('kgPanel');
        var title = document.getElementById('kgPanelTitle');
        var body = document.getElementById('kgPanelBody');
        if (!el || !title || !body) return;

        var nodeId = node.id();
        var nodeLabel = node.data('label') || nodeId;
        var nodeType = node.data('type') || 'service';
        var deprecated = node.data('deprecated');
        var statusHtml = deprecated ? ' <span style="color:#ef4444;font-size:0.55rem">⚠ 已停用</span>' : '';
        title.innerHTML = nodeLabel + ' <span style="font-size:0.6rem;opacity:0.6">' + nodeType + '</span>' + statusHtml;

        // 收集所有关联的三元组
        var triples = [];
        cy.edges().forEach(function (e) {
            var src = e.source().id(), tgt = e.target().id();
            var rel = e.data('relation') || 'connected';
            if (src === nodeId) {
                var t = cy.getElementById(tgt);
                triples.push({ dir: '→', source: nodeLabel, relation: rel, target: t.data('label') || tgt, targetId: tgt });
            } else if (tgt === nodeId) {
                var s = cy.getElementById(src);
                triples.push({ dir: '←', source: s.data('label') || src, relation: rel, target: nodeLabel, targetId: src });
            }
        });

        // 跳转日志页链接
        var logDir = node.data('log_dir') || node.data('folder') || '';
        var logPath = node.data('path') || '';
        var jumpDir = logDir || (logPath ? logPath.substring(0, logPath.lastIndexOf('/')) : '');
        var jumpHtml = '';
        if (jumpDir) {
            jumpHtml = '<a class="topo-jump-link" href="logs.html?folder=' + encodeURIComponent(jumpDir) + '" target="_blank" title="在新标签页搜索此目录日志">🔍 搜索此目录日志</a>';
        }

        if (triples.length === 0) {
            body.innerHTML = jumpHtml || '<div style="padding:12px;color:var(--text-tertiary);font-size:0.75rem">无关联关系</div>';
        } else {
            var html = jumpHtml;

            // ── 日志文件下载 ──
            var logFile = node.data('log_file') || '';
            var logDirSvc = node.data('log_dir') || '';
            var logPathNode = node.data('path') || '';
            var downloadPath = '';
            var downloadLabel = '';
            if (logFile && logDirSvc) {
                downloadPath = logDirSvc + '/' + logFile;
                downloadLabel = logFile;
            } else if (logPathNode) {
                downloadPath = logPathNode;
                downloadLabel = logPathNode.split('/').pop();
            }
            if (downloadPath) {
                var sizeMB = node.data('size_mb') || 0;
                html += '<div class="kg-download-row">';
                html += '<span class="kg-file-name" title="' + escapeHtml(downloadPath) + '">📄 ' + escapeHtml(downloadLabel) + '</span>';
                if (sizeMB) html += '<span class="kg-file-size">' + sizeMB.toFixed(1) + ' MB</span>';
                html += '<a class="kg-dl-btn" href="/api/download?path=' + encodeURIComponent(downloadPath) + '" title="下载日志文件">⬇</a>';
                html += '<button class="kg-dl-btn" onclick="window.open(\'logs.html?folder=' + encodeURIComponent(downloadPath) + '\')" title="查看此文件">👁</button>';
                html += '</div>';
            }

            // ── 中文元数据 ──
            var desc = node.data('desc') || '';
            var tags = node.data('tags') || [];
            if (desc || tags.length) {
                html += '<div class="kg-meta-card">';
                if (desc) html += '<div class="kg-meta-desc">' + escapeHtml(desc) + '</div>';
                if (tags.length) {
                    html += '<div class="kg-meta-tags">';
                    tags.forEach(function(t) { html += '<span class="kg-tag">' + escapeHtml(t) + '</span>'; });
                    html += '</div>';
                }
                html += '</div>';
            }

            html += '<div class="kg-triple-list">';
            triples.forEach(function (t) {
                var relClass = 'kg-rel ' + t.relation;
                html += '<div class="kg-triple-row" onclick="cy.getElementById(\'' + t.targetId + '\').select()">';
                if (t.dir === '→') {
                    html += '<span class="kg-node">' + escapeHtml(t.source) + '</span>';
                    html += '<span class="' + relClass + '">' + t.relation + '</span>';
                    html += '<span class="kg-node kg-target">' + escapeHtml(t.target) + '</span>';
                } else {
                    html += '<span class="kg-node">' + escapeHtml(t.source) + '</span>';
                    html += '<span class="' + relClass + '">' + t.relation + '</span>';
                    html += '<span class="kg-node kg-target">' + escapeHtml(t.target) + '</span>';
                }
                html += '</div>';
            });
            html += '</div>';
            
            // 查询关键词
            var keyword = node.data('keyword') || '';
            if (keyword) {
                html += '<div style="margin-top:8px;padding:6px 8px;background:var(--surface-secondary);border-radius:6px;font-size:0.65rem;font-family:monospace;color:var(--accent)">关键词: ' + escapeHtml(keyword) + '</div>';
            }
            
            body.innerHTML = html;
        }
        el.style.display = 'flex';
    };

    window.closeKgPanel = function () {
        var el = document.getElementById('kgPanel');
        if (el) el.style.display = 'none';
    };

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

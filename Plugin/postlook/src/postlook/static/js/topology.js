/**
 * postlook · 拓扑图页面逻辑
 */
var cy = null;
var topoInited = false;
var TOPO_DATA = null;
var TOPO_LOADING = false;

document.addEventListener('DOMContentLoaded', function() {
    // 构建拓扑数据
    window.buildTopoData = function(categories, services) {
        var cats = {};
        categories.forEach(function(c) { cats[c.id] = c; });
        var nodes = [{data:{id:'server',label:'postlook\n'+window.location.hostname,type:'server',weight:100},classes:'server'}];
        var edges = [];
        for (var k in cats) {
            var c = cats[k];
            nodes.push({data:{id:c.id,label:c.label,type:'category',cat:k,weight:60},classes:'category '+k});
            edges.push({data:{source:'server',target:c.id}});
        }
        for (var i=0;i<services.length;i++) {
            var s = services[i];
            var sz = Math.max(20, Math.min(50, (s.size_mb || 0.1) * 0.35 + 18));
            nodes.push({data:{id:s.id,label:s.name||s.id,type:'service',cat:s.category,desc:s.desc||'',logDir:s.log_dir||'',logFile:s.log_file||'',sizeMB:s.size_mb||0,weight:sz},classes:'service '+s.category});
            if (cats[s.category]) edges.push({data:{source:cats[s.category].id,target:s.id}});
        }
        return {nodes:nodes,edges:edges,services:services,categories:cats};
    };

    // 加载拓扑数据
    window.loadTopoData = function(callback) {
        if (TOPO_DATA) return callback(TOPO_DATA);
        if (TOPO_LOADING) { setTimeout(function(){ loadTopoData(callback); }, 200); return; }
        TOPO_LOADING = true;
        fetch('/api/topology-config').then(function(r){return r.json();}).then(function(data){
            TOPO_DATA = buildTopoData(data.categories || [], data.services || []);
            callback(TOPO_DATA);
        }).catch(function(){
            var cats = [
                {id:'apps',label:'应用系统',color:'#0abde3'},
                {id:'planner',label:'路径规划',color:'#f87171'},
                {id:'middleware',label:'中间件',color:'#fbbf24'},
                {id:'system',label:'系统日志',color:'#4ade80'},
                {id:'database',label:'数据库',color:'#a855f7'}
            ];
            var svcs = [
                {id:'gateway',name:'Gateway',category:'apps',log_dir:'/main/app/gateway/logs',log_file:'GATEWAY.log',size_mb:48},
                {id:'bms',name:'BMS',category:'apps',log_dir:'/main/app/bms/logs',log_file:'BMS.log',size_mb:96},
                {id:'nacos',name:'Nacos',category:'middleware',log_dir:'/main/server/nacos/logs',log_file:'nacos.log',size_mb:14},
                {id:'messages',name:'messages',category:'system',log_dir:'/var/log',log_file:'messages',size_mb:4},
                {id:'mariadb',name:'MariaDB',category:'database',log_dir:'/main/server/mysql',log_file:'slow-sql',size_mb:1}
            ];
            TOPO_DATA = buildTopoData(cats, svcs);
            callback(TOPO_DATA);
        });
    };

    // 放射布局计算
    window.calcRadialLayout = function(topoData) {
        var pos = {};
        var cats = Object.keys(topoData.categories);
        for (var i = 0; i < cats.length; i++) {
            var cat = topoData.categories[cats[i]];
            var a = (2 * Math.PI * i) / cats.length - Math.PI / 2;
            var cx = Math.cos(a) * 260, cy = Math.sin(a) * 260;
            pos[cat.id] = { x: cx, y: cy };
            var svcs = topoData.services.filter(function(s) { return s.category === cats[i]; });
            var svcLen = svcs.length;
            var arc = Math.min(3.5, Math.max(0.4, svcLen * 0.13));
            var dist = 110 + Math.max(0, svcLen - 8) * 8;
            for (var j = 0; j < svcLen; j++) {
                var sa = svcLen <= 1 ? a : a - arc / 2 + (arc * j / (svcLen - 1));
                pos[svcs[j].id] = { x: cx + Math.cos(sa) * dist, y: cy + Math.sin(sa) * dist };
            }
        }
        pos['server'] = { x: 0, y: 0 };
        return pos;
    };

    // 初始化拓扑
    function initTopology() {
        if (topoInited) { if (cy) { cy.resize(); cy.fit(undefined, 30); } return; }
        topoInited = true;
        var container = document.getElementById('cy');
        if (!container) return;
        var statusEl = document.getElementById('topoStatus');
        if (statusEl) statusEl.textContent = '加载配置中...';
        loadTopoData(function(data) {
            if (!data || !data.nodes) return;
            _initTopoWithData(container, data);
        });
    }

    // 渲染拓扑图
    function _initTopoWithData(container, data) {
        cy = cytoscape({
            container: container,
            elements: { nodes: data.nodes, edges: data.edges },
            style: [
                { selector: '.server', style: { 'shape':'ellipse','background-color':'#818cf8','background-opacity':0.2,'label':'data(label)','color':'#e0e0f0','font-size':'13px','font-weight':'bold','text-valign':'center','text-halign':'center','width':110,'height':110,'border-width':2,'border-color':'#818cf8','text-wrap':'wrap','text-max-width':'80px' } },
                { selector: '.category', style: { 'shape':'ellipse','label':'data(label)','color':'#c0c0e0','font-size':'12px','font-weight':'bold','text-valign':'center','text-halign':'center','width':75,'height':75,'border-width':2,'border-color':'#a0a0c0' } },
                { selector: '.apps', style: { 'background-color':'#0abde3','background-opacity':0.18,'border-color':'#0abde3' } },
                { selector: '.planner', style: { 'background-color':'#f87171','background-opacity':0.18,'border-color':'#f87171' } },
                { selector: '.middleware', style: { 'background-color':'#fbbf24','background-opacity':0.18,'border-color':'#fbbf24' } },
                { selector: '.system', style: { 'background-color':'#4ade80','background-opacity':0.18,'border-color':'#4ade80' } },
                { selector: '.database', style: { 'background-color':'#a855f7','background-opacity':0.18,'border-color':'#a855f7' } },
                { selector: '.service', style: { 'shape':'ellipse','label':'data(label)','color':'#e8e0f0','font-size':'10px','text-valign':'center','text-halign':'center','width':'data(weight)','height':'data(weight)','border-width':2 } },
                { selector: '.service:selected', style: { 'border-width':3,'border-color':'#fff' } },
                { selector: 'edge', style: { 'width':1.2,'line-color':'rgba(129,140,248,0.35)','curve-style':'bezier','opacity':0.7,'line-dash-pattern':[4,8],'line-dash-offset':0 } }
            ],
            layout: { name:'preset', positions: calcRadialLayout(data), animate:true, animationDuration:800 },
            wheelSensitivity: 0.3, userZoomingEnabled: true, userPanningEnabled: true, minZoom: 0.15, maxZoom: 3,
            autoungrabify: false, autounselectify: false
        });

        // 状态更新
        document.getElementById('topoStatus').textContent = (data.services.length + 5) + ' 节点就绪';

        // 布局完成后再启动动画
        setTimeout(function() {
            cy.resize();
            cy.fit(undefined, 40);
            document.getElementById('topoStatus').textContent = (data.services.length + 5) + ' 节点 · 滚轮缩放';

            // 浮动动画
            var floatPhases = {}, floatTime = 0, basePos = {};
            cy.nodes().forEach(function(n) { basePos[n.id()] = {x:n.position('x'),y:n.position('y')}; floatPhases[n.id()] = Math.random()*Math.PI*2; });
            cy.on('free', '.service', function(evt) {
                var n = evt.target, id = n.id();
                if (basePos[id]) n.animate({position:basePos[id]},{duration:300});
            });
            setInterval(function() {
                floatTime += 0.05;
                cy.nodes().forEach(function(n) {
                    var id = n.id(), o = basePos[id];
                    if (!o || n.grabbed()) return;
                    floatPhases[id] += 0.03;
                    var p = floatPhases[id];
                    n.position({x: o.x + Math.sin(p*0.7+floatTime)*12 + Math.cos(p*1.3)*10, y: o.y + Math.cos(p*0.9+floatTime)*12 + Math.sin(p*1.1)*10});
                    n.style('width', n.data('weight')*(1+Math.sin(p)*0.04));
                    n.style('height', n.data('weight')*(1+Math.sin(p)*0.04));
                });
            }, 40);
        }, 900); // 布局动画 800ms 结束后启动

        // 点击事件
        cy.on('tap', '.service', function(evt) { showTopoDetail(evt.target); });
        cy.on('tap', function(evt) { if(evt.target===cy) closeTopoDetail(); });

        // 左侧图层
        var layersDiv = document.getElementById('topoLayers');
        if (layersDiv) {
            var h = '<div class="sb-labels">';
            for (var k in data.categories) {
                var c = data.categories[k];
                var count = data.services.filter(function(s){return s.category===k;}).length;
                h += '<label class="sb-label"><input type="checkbox" checked data-cat="'+k+'" onchange="toggleLayer(\''+k+'\',this.checked)"> <span class="sb-legend-dot" style="background:'+c.color+'"></span> '+c.label+' <span class="count">'+count+'</span></label>';
            }
            h += '</div>';
            layersDiv.innerHTML = h;
        }

        // 左侧图例
        var legendDiv = document.querySelector('.sb-legend');
        if (legendDiv) {
            var h = '';
            for (var k in data.categories) {
                var c = data.categories[k];
                h += '<div class="sb-legend-item"><span class="sb-legend-dot" style="background:'+c.color+'"></span>'+c.label+'</div>';
            }
            legendDiv.innerHTML = h;
        }
    }

    // 图层切换
    window.toggleLayer = function(cat, show) {
        if (!cy) return;
        if (show) { cy.nodes('.' + cat).style('display','element'); }
        else { cy.nodes('.' + cat).style('display','none'); }
    };

    // 搜索过滤
    window.filterTopoNodes = function(query) {
        if (!cy) return;
        var q = query.toLowerCase();
        cy.nodes('.service').forEach(function(n) {
            var label = (n.data('label')||'').toLowerCase();
            var desc = (n.data('desc')||'').toLowerCase();
            n.style('display', (q === '' || label.indexOf(q) >= 0 || desc.indexOf(q) >= 0) ? 'element' : 'none');
        });
    };

    // 显示详情
    window.showTopoDetail = function(node) {
        try {
            var el = document.getElementById('topoDetail');
            var name = document.getElementById('topoDetailName');
            var body = document.getElementById('topoDetailBody');
            if (!el || !name || !body) return;
            el.style.display = 'flex';
            var label = node.data('label'), logDir = node.data('logDir'), logFile = node.data('logFile'), desc = node.data('desc')||'', sizeMB = node.data('sizeMB')||0;
            name.textContent = label + (desc ? ' — ' + desc : '');
            var html = '<div style="margin-bottom:8px;color:var(--text-tertiary);font-size:0.75rem">路径: '+(logDir||'—')+' | 主日志: '+(logFile||'—')+' | '+(sizeMB?sizeMB.toFixed(1)+' MB':'')+'</div>';
            html += '<div style="margin-bottom:4px;font-weight:600;font-size:0.8rem">日志文件</div>';
            html += '<div id="topoFileList" style="margin-bottom:10px">加载中...</div>';
            html += '<div style="font-weight:600;font-size:0.8rem">最新预览</div>';
            html += '<div class="log-preview" id="topoLogPreview">加载中...</div>';
            html += '<div style="margin-top:10px;display:flex;gap:6px">';
            if (logFile) html += '<button class="file-actions" style="padding:4px 12px" onclick="window.open(\'/api/download?path='+encodeURIComponent((logDir||'')+'/'+logFile)+'\')">⬇ 下载</button>';
            html += '<button class="file-actions" style="padding:4px 12px" onclick="closeTopoDetail()">关闭</button></div>';
            body.innerHTML = html;

            fetch('/api/files').then(function(r){return r.json();}).then(function(data){
                var fl = document.getElementById('topoFileList');
                if (!fl) return;
                var items = '';
                if (data.directories && logDir) {
                    for (var i=0;i<data.directories.length;i++){
                        var d=data.directories[i];
                        if (d.path===logDir||d.path.indexOf(logDir+'/')===0){
                            for (var j=0;j<Math.min(d.files.length,10);j++){
                                var f=d.files[j];
                                items += '<div class="file-row"><span class="file-name" title="'+f.path+'">'+f.name+'</span><span class="file-size">'+formatBytes(f.size)+'</span><div class="file-actions"><button onclick="window.open(\'/api/download?path='+encodeURIComponent(f.path)+'\')">⬇</button><button onclick="viewTopoLog(\''+encodeURIComponent(f.path)+'\')">👁</button></div></div>';
                            }
                            break;
                        }
                    }
                }
                fl.innerHTML = items || '暂无文件';
            }).catch(function(){ var fl=document.getElementById('topoFileList'); if(fl)fl.innerHTML='加载失败'; });

            if (logFile && logDir) {
                fetch('/api/logs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({folder:logDir,pattern:logFile,tail:true,line_start:1,line_end:60,recent_files:1})})
                    .then(function(r){return r.json();}).then(function(data){
                        var lp = document.getElementById('topoLogPreview');
                        if (!lp) return;
                        var lines = '';
                        if (data.results) for (var i=0;i<data.results.length;i++){ var c=data.results[i].content; lines += '<div style="font-size:0.68rem;white-space:nowrap;line-height:1.3">'+escapeHtml(c)+'</div>'; }
                        lp.innerHTML = lines || '暂无日志';
                    }).catch(function(){ var lp=document.getElementById('topoLogPreview'); if(lp)lp.innerHTML='加载失败'; });
            }
        } catch(e) { console.error('topoDetail error:', e); }
    };

    window.closeTopoDetail = function() { var el = document.getElementById('topoDetail'); if (el) el.style.display = 'none'; };
    window.viewTopoLog = function(path) { window.open('logs.html?folder=' + encodeURIComponent(decodeURIComponent(path))); };

    // 启动
    initTopology();
});

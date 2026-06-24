
# postlook

轻量、安全的日志 HTTP 查询与实时监控 Web 应用，支持自定义规则着色、快捷查询保存、实时滚动刷新。

## 项目目标

- 通过 POST 请求，在指定文件夹内按文件名、关键字、行数等条件查询日志内容。
- 严格限制每次返回行数，避免大响应。
- 路径白名单机制，防止越权读取任意文件。
- 支持关键字高亮 + 自定义规则着色 + 注解标签。
- 快捷查询保存（TOML 格式），可一键复用常用查询条件。
- 实时滚动刷新，增量追加新日志行。

端口默认 5011，前端为 macOS 风格暗黑主题 UI，支持亮色/暗黑切换。

## 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v0.1.0 | 2025-05 | 基础日志查询 + Web UI + TOML 配置管理 |
| v0.2.0 | 2025-05 | 批量查询 + 气泡筛选 + 文件组折叠 |
| v0.3.0 | 2025-06 | 实时滚动刷新 + 自动查询 + rows 展开 |
| v0.4.0 | 2025-06 | 规则引擎 + 自定义着色/注解 + 拓扑/服务状态 |
| v0.5.0 | 2026-06 | 报文调试页面 + 下载接口 |
| **v0.6.0** | **2026-06** | **快捷查询保存 (date-queries) + 搜索高亮 + 架构分层重构** |
| v0.7.0 | 2026-06 | 拓扑自动发现（supervisor + /main 扫描） |
| v0.8.x | 2026-06 | concentric→breadthfirst→preset 布局演进 |
| v0.9.x | 2026-06 | 放射状思维导图 + 呼吸灯动画 |
| **v0.10.x** | **2026-06** | **多视图切换（横向/纵向/放射/图谱）+ 节点尺寸自适应** |
| v0.11.0 | 2026-06 | dagre 布局引擎集成（替代手写布局） |
| v0.12.0 | 2026-06 | 知识图谱视图 + 多类型节点 + 三元组面板 |
| **v0.13.0** | **2026-06** | **D3 力仿真引擎（水面漂浮拖拽 + 磁铁互斥）** |

## Web 前端

| 页面 | 路径 | 功能 |
|------|------|------|
| 日志查询 | `/logs.html` | 关键字搜索/实时滚动/文件分组/高亮/规则着色/快捷查询 |
| 配置管理 | `/config.html` | TOML 编辑器 + 在线热更新 |
| 服务状态 | `/status.html` | 在线状态检测 + 白名单目录文件浏览器 |
| 拓扑 | `/topology.html` | 多视图拓扑图（横向/纵向/放射/图谱） |
| 报文调试 | `/debug.html` | TCP 连接调试 + 报文收发 |

### 快捷查询 (v0.6.0)

左侧栏「快捷查询」支持保存常用查询条件为 TOML 文件：

- **保存**：输入日志路径 + 筛选条件后点击「保存」，输入名称即可存入侧栏
- **加载**：点击侧栏条目自动填入表单并执行查询
- **删除**：悬停显示 ✕ 按钮删除

配置文件位于 `config/date/*.toml`，可手动编辑或通过 API 管理。

### 规则引擎 (v0.4.0)

`config/rules.toml` 定义日志着色和注解规则：

- 关键字匹配 → 整行着色（左边框 + 背景色）
- 正则匹配 → 同关键字
- Hex 匹配 → 正常化后匹配（忽略空格大小写）
- 注解标签 → 匹配行前缀显示自定义徽标

34 条内置规则（错误/异常/超时/电梯/调度等），可通过配置管理页面编辑。

### 拓扑图 · 多视图引擎 (v0.10.0+)

拓扑图支持 4 种视图一键切换，底层数据为同一份文件树/知识图谱结构：

```
┌───────────────┬──────────────────┬─────────────────────┐
│ 视图           │ 引擎              │ 布局算法              │
├───────────────┼──────────────────┼─────────────────────┤
│ ⇢ 横向         │ dagre (284KB)    │ 分层有向图 rankDir=LR │
│ ⇣ 纵向         │ dagre            │ 分层有向图 rankDir=TB │
│ ◎ 放射         │ 手写递归算法      │ 比例扇形 + 自适应半径  │
│ ◉ 图谱         │ D3 (274KB)       │ forceSimulation 连续仿真│
└───────────────┴──────────────────┴─────────────────────┘
```

#### 数据流

```
config/app.toml (root_dirs)
        │
        ▼
  config.py
  ├─ build_topology_tree()  → /api/topology-config → 横向/纵向/放射
  └─ build_knowledge_graph() → /api/topology-kg     → 图谱(D3)
  　　　　　　　　　　　　　　　　├─ 服务节点(圆)
  　　　　　　　　　　　　　　　　├─ 日志节点(小圆)
  　　　　　　　　　　　　　　　　├─ 错误查询(红圆, 来自 date/*.toml)
  　　　　　　　　　　　　　　　　└─ 多关系边: produces/has_query/runs_on/belongs_to
```

#### D3 力仿真引擎 (v0.13.0, 图谱视图)

```
d3.forceSimulation()
  ├─ forceLink(spring)    距离=70, 强度=0.25  → 连线节点弹簧引力
  ├─ forceManyBody(charge) 强度=-200           → 全局节点磁铁斥力
  ├─ forceCenter()                              → 向心力防飘出
  ├─ alphaDecay(0.012)                          → 水面漂浮停缓
  └─ velocityDecay(0.45)                        → 摩擦阻尼

拖拽物理:
  grab → 固定节点(fx,fy)
  drag → 更新固定点 + 加热仿真(alpha=0.25) → 涟漪扩散
  free → 释放节点 + 惯性漂移 → 缓慢停下
```

#### 前端依赖

| 文件 | 大小 | 用途 |
|------|------|------|
| `lib/cytoscape.min.js` | 358KB | 图形渲染 + 交互（pan/zoom/click） |
| `lib/dagre.min.js` | 278KB | 分层布局引擎（横向/纵向视图） |
| `lib/cytoscape-dagre.js` | 13KB | dagre → Cytoscape 适配器 |
| `lib/d3.v7.min.js` | 274KB | 力仿真引擎（图谱视图） |
| `js/topology.js` | ~1000行 | 4 视图切换 + 布局调度 + 交互逻辑 |

所有依赖均为本地文件，离线部署可用。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/logs` | 查询日志内容 |
| GET | `/api/logs/self` | 查看 postlook 自身日志 |
| GET | `/api/config` | 获取当前 TOML 配置 |
| POST | `/api/config` | 保存配置（热更新） |
| GET | `/api/rules` | 获取着色/注解规则 |
| GET | `/api/date-queries` | 获取所有保存的快捷查询 |
| POST | `/api/date-queries` | 保存/覆盖快捷查询 |
| DELETE | `/api/date-queries/{filename}` | 删除指定快捷查询 |
| GET | `/api/files` | 列出白名单目录文件树 |
| GET | `/api/scan-dirs` | 扫描指定路径下 log/logs 目录 |
| GET | `/api/download` | 下载日志文件（白名单 + 扩展名管控） |
| GET | `/api/health` | 健康检查 |
| GET | `/api/help` | 接口文档和使用说明 |
| GET | `/docs` | Swagger UI 交互式文档 |
| — | — | **拓扑 (v0.10.0+)** | — |
| GET | `/api/topology-config` | 文件树拓扑数据 → 横向/纵向/放射视图 |
| GET | `/api/topology-kg` | 知识图谱数据 → 图谱视图（多类型节点+关系边） |
| GET | `/api/topology/discover` | 自动发现新服务（supervisor + 目录扫描） |
| POST | `/api/topology/merge` | 合并选中服务到拓扑配置 |

### POST /api/logs 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `folder` | string | 必填 | 目录路径或文件路径（白名单内） |
| `pattern` | string | `*.log` | 文件名通配符（目录模式） |
| `keyword` | string | 可选 | 搜索关键字，不区分大小写 |
| `line_start` | int | 1 | 起始行号 |
| `line_end` | int | 100 | 结束行号（含） |
| `tail` | bool | true | 无关键字时从尾部读取 |
| `recent_files` | int | 10 | 扫描最近修改的 N 个文件 |

### 安全机制
- 路径白名单：`config/app.toml` 中配置 `root_dirs`，支持多个目录
- 环境变量 `POSTLOOK_ROOT` 可覆盖白名单（逗号分隔）
- 不跟随符号链接到白名单外
- 非白名单路径返回 403
- 下载接口双重管控：白名单路径 + 扩展名白名单

## 技术栈

- **语言**：Python 3.9+
- **Web 框架**：FastAPI + Uvicorn
- **数据校验**：Pydantic
- **配置解析**：tomli（TOML）
- **部署**：Supervisor + 离线 pip 包

## 项目结构

```
postlook/
├── readme.md
├── .gitignore
├── config/                         # 配置文件
│   ├── app.toml                   # 主配置（热加载）
│   ├── env.toml                   # 环境配置（进.gitignore）
│   ├── rules.toml                 # 规则配置（着色/注解）
│   ├── debug.toml                 # 调试连接配置
│   ├── old/                       # 备份及老配置文件
│   ├── template/                  # 配置文件模板
│   │   ├── app.toml
│   │   ├── env.toml
│   │   ├── rules.toml
│   │   ├── debug.toml
│   │   └── date/                  # 快捷查询模板
│   └── date/                      # 保存的快捷查询 (*.toml)
├── deploy/                         # 多平台离线部署
│   ├── deploy.sh                  # 一键部署入口
│   ├── deploy.conf                # 部署配置参数
│   ├── README.md                  # 部署文档
│   ├── lib/                       # 公共函数库
│   ├── vendor_packages/           # 离线依赖包（按 Python ABI 分层）
│   │   ├── common/                # 纯 Python 包（py3-none-any）
│   │   ├── cp39/                  # Python 3.9 ABI 专用
│   │   └── cp311/                 # Python 3.11 ABI 专用
│   └── platform/                  # 平台专属资源
├── src/postlook/                   # 源代码
│   ├── app.py                     # FastAPI 应用入口
│   ├── routes.py                  # API 路由
│   ├── scanner.py                 # 文件扫描与内容读取
│   ├── config.py                  # 配置加载（支持热更新 + 健康自检）
│   ├── debug_service.py           # TCP 报文调试服务
│   └── static/                    # 前端静态文件
│       ├── index.html             # 主页面
│       ├── logs.html              # 日志查询（架构分层: State→DOM→Init→Events→API→Render→Query→Live→Utils→Feedback→DateQueries）
│       ├── config.html            # 配置管理
│       ├── status.html            # 服务状态
│       ├── topology.html          # 拓扑视图
│       ├── debug.html             # 报文调试
│       ├── style.css              # macOS 暗黑风格全局样式
│       └── js/                    # JavaScript 模块
│           ├── common.js          # 公共：主题/转义/高亮/规则引擎
│           ├── logs.js            # 日志查询页面逻辑
│           ├── config.js          # 配置管理页面逻辑
│           ├── status.js          # 服务状态页面逻辑
│           ├── topology.js        # 拓扑多视图引擎 + D3/Dagre/Cytoscape
│           └── debug.js           # 调试页面逻辑
│       └── lib/                    # 离线前端依赖
│           ├── cytoscape.min.js   # 图形渲染引擎 (358KB)
│           ├── dagre.min.js       # 分层布局引擎 (278KB)
│           ├── cytoscape-dagre.js # dagre→Cytoscape (13KB)
│           └── d3.v7.min.js       # 力仿真引擎 (274KB)
├── test/                          # 测试
├── doc/api/                       # API 文档
├── logs/                          # 日志（进.gitignore）
├── data/                          # 运行时数据（进.gitignore）
├── backup/                        # 备份（进.gitignore）
├── dev/                           # 调试（进.gitignore）
├── plans/                         # 计划（进.gitignore）
└── skill/                         # skill 文件
```

## logs.js 架构 (v2.1)

```
╔══════════════════════════════════╗
║  State     模块状态（集中管理）     ║
╠══════════════════════════════════╣
║  DOM       cacheEls() 统一引用    ║
╠══════════════════════════════════╣
║  Init      init() 入口 ──────────┐║
║            ├─ cacheEls()         │║
║            ├─ loadRules() ← 补   │║
║            ├─ loadDateQueries()  │║
║            ├─ bindSidebar/Form/  │║
║            │  Folder/Button()    │║
║            └─ loadVersion()      │║
╠══════════════════════════════════╣
║  Events    侧栏/表单/按钮 绑定     ║
╠══════════════════════════════════╣
║  API       fetchLogs() +         ║
║            loadDateQueries()     ║
╠══════════════════════════════════╣
║  Render    renderLine() ← 共用   ║
║            ├─ escapeHtml         ║
║            ├─ highlightKeyword   ║
║            └─ applyRulesAndAnn.  ║
║            renderResults()       ║
║            appendLiveLines()     ║
╠══════════════════════════════════╣
║  Query     doQuery / doLiveQuery ║
╠══════════════════════════════════╣
║  Live      start/stop/schedule   ║
╠══════════════════════════════════╣
║  Utils     chip/history/shell    ║
╠══════════════════════════════════╣
║  Feedback  notify() 统一通知     ║
╠══════════════════════════════════╣
║  DateQ.    快捷查询 CRUD         ║
╚══════════════════════════════════╝
```

## 开发路线图

### Phase 1：基础查询 ✅
- [x] scanner.py 文件发现/关键字搜索/tail/行号范围
- [x] routes.py 与 Pydantic 模型
- [x] 安全校验与错误处理
- [x] Web 前端（日志查询 + 配置管理 + 服务状态）
- [x] 配置热更新
- [x] Supervisor 离线部署脚本

### Phase 2：增强查询 ✅
- [x] 批量查询 + 气泡筛选 + 文件组折叠
- [x] 实时滚动刷新 + 自动查询
- [x] 规则引擎：自定义着色 + 注解标签（34 条内置规则）
- [x] 拓扑/服务状态可视化
- [x] 快捷查询保存与一键加载 (date-queries)
- [x] 搜索关键字高亮 + CSS 匹配修复
- [x] 架构分层重构：State→DOM→Init→Events→API→Render→Query→Live→Utils→Feedback→DateQueries
- [ ] 多关键字 AND/OR 搜索
- [ ] 正则表达式匹配
- [ ] 时间范围过滤
- [ ] 结果分页

### Phase 3：实时监控
- [ ] WebSocket/SSE 端点实时推送新日志行
- [ ] 前端实时日志流展示

### Phase 4：生产就绪
- [ ] Docker 镜像
- [ ] 访问频率限制与鉴权

## 快速开始

### 开发模式
```bash
cd Plugin/postlook
pip install fastapi uvicorn pydantic tomli
python3 -m uvicorn src.postlook.app:app --host 0.0.0.0 --port 5011 --reload
```

### 生产部署
```bash
cd Plugin/postlook
sudo bash deploy/deploy.sh
```

启动后访问：
- 前端页面：http://localhost:5011
- API 文档：http://localhost:5011/docs
- 接口帮助：http://localhost:5011/api/help
- 健康检查：http://localhost:5011/api/health

### curl 示例
```bash
# 查看文件前20行
curl -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{"folder": "/var/log/syslog", "line_start": 1, "line_end": 20}'

# 关键字搜索
curl -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{"folder": "/var/log", "keyword": "error", "line_start": 1, "line_end": 500}'

# 保存快捷查询
curl -X POST http://localhost:5011/api/date-queries \
  -H "Content-Type: application/json" \
  -d '{"name":"Gateway错误","folder":"/main/app/gateway/logs","pattern":"GATEWAY.log","keyword":"ERROR"}'

# 查看保存的快捷查询
curl http://localhost:5011/api/date-queries

# 查看配置
curl http://localhost:5011/api/config

# 接口帮助
curl http://localhost:5011/api/help
```

## 为什么叫 postlook？

**post** = 通过 POST 请求获取；**look** = 快速看一眼日志。轻巧、直接、RESTful 风格的工具。

---

*欢迎贡献和反馈。*

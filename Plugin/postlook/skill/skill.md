# postlook skill

## 项目概述
**postlook** — 轻量、安全的日志 HTTP 查询服务。通过 POST 请求在指定文件夹内按文件名、关键字、行号范围等条件查询日志，支持 Web UI、配置热更新、路径白名单安全机制。

当前版本：v0.13.0

## 技术栈
| 层级 | 选型 | 说明 |
|------|------|------|
| 语言 | Python 3.9+ | 兼容 CentOS 7 源码编译和预编译包 |
| Web 框架 | FastAPI + Uvicorn | 异步高性能 |
| 数据校验 | Pydantic v2 | Request/Response 模型 |
| 配置解析 | tomli (Python <3.11) / tomllib (3.11+) | TOML 格式 |
| 前端 | 原生 HTML/CSS/JS + Cytoscape/D3/Dagre | 拓扑图多视图引擎 |
| 布局引擎 | dagre 分层 / D3 力仿真 / 手写放射 | 4 视图切换，全部离线 |
| 部署 | Supervisor + 离线 pip 包 | 支持 CentOS 7 离线部署 |

## 项目结构
```
Plugin/postlook/
├── src/postlook/               # 源代码
│   ├── app.py                  # FastAPI 入口，版本号 __version__
│   ├── config.py               # 配置加载/热更新/环境变量覆盖
│   ├── routes.py               # 全部 API 路由定义
│   ├── scanner.py              # 文件扫描与内容读取核心
│   ├── debug_service.py        # 报文调试：TCP发送/Ping检测/报文管理 (v0.4.0)
│   └── static/                 # 前端 SPA
│       ├── index.html          # 主页面（六卡片布局）
│       ├── style.css           # Mac 风格样式（暗黑/亮色）
│       ├── logs.html           # 日志查询
│       ├── config.html         # 配置管理
│       ├── status.html         # 服务状态
│       ├── topology.html       # 拓扑图（4视图切换）
│       ├── debug.html          # 报文调试 (v0.4.0)
│       ├── app.js              # 旧版前端逻辑
│       ├── js/                 # 模块化 JS
│       │   ├── common.js       # 公共（主题/SVG/工具）
│       │   ├── logs.js         # 日志查询
│       │   ├── config.js       # 配置管理
│       │   ├── status.js       # 服务状态
│       │   ├── topology.js     # 拓扑多视图引擎 (~1000行)
│       │   └── debug.js        # 报文调试 (v0.4.0)
│       └── lib/                # 离线前端依赖 (v0.10.0+)
│           ├── cytoscape.min.js   # 图形渲染引擎 (358KB)
│           ├── dagre.min.js       # 分层布局引擎 (278KB)
│           ├── cytoscape-dagre.js # dagre→Cytoscape (13KB)
│           └── d3.v7.min.js       # 力仿真引擎 (274KB)
├── config/                     # 配置文件
│   ├── env.toml                # 运行配置（.gitignore）
│   └── template/env.toml       # 配置模板
├── deploy/                     # 多平台离线部署
│   ├── deploy.sh               # 一键部署入口（自动检测 OS + Python ABI）
│   ├── deploy.conf             # 部署配置参数
│   ├── README.md               # 部署文档
│   ├── lib/                    # 公共函数库
│   │   ├── common.sh           # 日志输出 / 错误处理
│   │   ├── detect.sh           # OS / Python / ABI 检测
│   │   ├── python.sh           # Python 环境准备 + venv
│   │   ├── deps.sh             # 离线依赖安装（ABI 感知选包）
│   │   └── supervisor.sh       # Supervisor 配置生成 + 服务启动
│   ├── vendor_packages/        # 离线 pip 依赖包（按 ABI 分层）
│   │   ├── common/             # 纯 Python 包（py3-none-any，共享）
│   │   ├── cp39/               # Python 3.9 ABI（pydantic_core 等）
│   │   └── cp311/              # Python 3.11 ABI
│   └── platform/               # 平台专属资源
│       ├── centos7/rpms/       # CentOS 7 devel RPM + Python 源码
│       └── openEuler/          # openEuler 专用（空壳占位）
├── skill/                      # Skill 文件
│   ├── skill.md                # 本文件
│   ├── api_skill.md            # API 实战操作指南
│   ├── fywds_skill.md          # FYWDS 服务日志分析
│   ├── troubleshoot_skill.md   # 远程排查方法论
│   └── rcs_skill/
│       └── rcslog_skill.md     # RCS 日志目录白名单
├── test/                       # 测试
│   └── start.md                # 前端设计文档（非测试脚本）
├── doc/
│   └── api/                    # API 文档
├── logs/                       # 日志（.gitignore）
├── plans/                      # 计划（.gitignore）
├── report/                     # 排查报告（.gitignore）
├── backup/                     # 备份（.gitignore）
└── dev/                        # 调试脚本（.gitignore）
├── data/                       # 报文调试数据 (v0.4.0)
│   └── messages.toml           # 报文分组配置（用户可编辑，支持热更新）
```

## API 接口（全部 9 个端点）

| 方法 | 路径 | 说明 | 响应模型 |
|------|------|------|----------|
| POST | `/api/logs` | 查询日志内容 | `LogQueryResponse` |
| GET | `/api/logs/self` | 查看 postlook 自身日志 | 自定义 JSON |
| GET | `/api/download` | 下载日志文件（安全管控） | 文件流 `application/octet-stream` |
| GET | `/api/config` | 获取当前 TOML 配置及解析值 | `{content, root_dirs, ...}` |
| POST | `/api/config` | 保存 TOML 配置（热更新） | `{status, message}` |
| GET | `/api/scan-dirs` | 扫描路径下 log/logs 目录 | `{base, exists, dirs[]}` |
| GET | `/api/files` | 列出白名单目录文件树 | `{directories[]}` |
| GET | `/api/health` | 健康检查 | `{status, version}` |
| GET | `/api/help` | 接口文档与使用说明 | 全量 endpoint 详情 |
| GET | `/docs` | Swagger UI 交互式文档 |
| — | — | **拓扑/图谱 (v0.10.0+)** | — |
| GET | `/api/topology-config` | 文件树拓扑（横向/纵向/放射视图） | `{nodes[], edges[]}` |
| GET | `/api/topology-kg` | 知识图谱（图谱视图 + D3力仿真） | `{nodes[], edges[]}`, 多类型节点+关系边 |
| GET | `/api/topology/discover` | 自动发现新服务（supervisor+目录） | `{candidates[], existing_ids[]}` |
| POST | `/api/topology/merge` | 合并选中服务到拓扑配置 | `{status, added, skipped}` |
| — | — | **报文调试 (v0.4.0)** | — |
| POST | `/api/debug/test-connection` | Ping + TCP 端口检测 | `{ping, port}` |
| GET | `/api/debug/messages` | 获取报文分组数据 | `{groups[], count}` |
| GET | `/api/debug/messages-toml` | 获取 messages.toml 原文 | 纯文本 |
| POST | `/api/debug/messages` | 保存报文数据（热更新） | `{status}` |
| POST | `/api/debug/reload` | 热重新加载报文配置 | `{status}` |
| GET | `/api/debug/config` | 获取调试连接配置 | `{config, toml}` |
| POST | `/api/debug/config` | 保存连接配置（热更新） | `{status}` |
| POST | `/api/debug/send` | 发送 hex 报文（一连接一断） | `{sent_hex, received_hex, total_ms}` |

### POST /api/logs 详细参数

| 参数 | 类型 | 默认值 | 校验 | 说明 |
|------|------|--------|------|------|
| `folder` | string | 必填 | - | 白名单内目录或文件绝对路径 |
| `pattern` | string | `*.log` | - | 文件名通配符（目录模式） |
| `keyword` | string? | null | - | 搜索关键字，不区分大小写 |
| `line_start` | int | 1 | ge=1 | 起始行号 |
| `line_end` | int | 100 | ≥line_start | 结束行号（含） |
| `tail` | bool | true | - | 无关键字时从尾部读取 |
| `recent_files` | int | 10 | 1~50 | 扫描最近修改的 N 个文件 |

### 安全机制
- **路径白名单**：`config/env.toml` → `[logs].root_dirs`，支持多个目录
- **环境变量覆盖**：`POSTLOOK_ROOT` 可覆盖白名单（逗号分隔）
- **符号链接拒绝**：`scanner.py#find_files` 跳过 `is_symlink()`
- **路径逃逸防御**：`resolve_folder()` 检查 resolved 路径是否在任一白名单目录下
- **下载扩展名白名单**：仅允许 `.log/.out/.txt/.gz/.dmp/.hprof/.core` 等日志类文件下载
- **下载大小上限**：默认 200MB，可配置 `max_download_size`，硬上限 1GB
- **XSS 防护**：前端 `escapeHtml()` 转义特殊字符后才插入 DOM

## 核心模块

### `app.py` — 应用入口
```
__version__ = "0.1.0"   ← 版本号唯一来源
```
- 实例化 FastAPI，挂载 API 路由 → 挂载静态文件(SPA)
- 静态文件挂载必须在 API 路由之后（防止 SPA 的根路径覆盖 `/api/`）
- 内置 `/api/health` 健康检查端点

### `config.py` — 配置模块
```
CONFIG_PATH = PROJECT_ROOT / "config" / "env.toml"
```
- 线程锁保护热更新（`reload_config()`）
- 加载优先级：环境变量 `POSTLOOK_ROOT` > TOML 配置 > 默认值
- `get_config_toml()` 回退链：`env.toml` → `template/env.toml` → 硬编码默认值
- 导出全局变量：`ROOT_DIRS`, `MAX_LINES`, `DEFAULT_LINES`, `DEFAULT_RECENT_FILES`, `DEFAULT_THEME`, `SERVER_HOST`, `SERVER_PORT`

### `scanner.py` — 文件扫描与读取
```
┌─────────────────────────────────────────────────┐
│  scan_logs()       ← 对外主入口               │
│  ├─ resolve_folder() → 路径校验 + 白名单检查  │
│  ├─ find_files()     → 按通配符 + 时间排序    │
│  └─ search_lines()   → 按行号/关键字/方向读取 │
└─────────────────────────────────────────────────┘
```
- **`resolve_folder(folder, root_dirs)`**: 绝对路径检查白名单，相对路径依次尝试每个 root_dir
- **`find_files(folder, pattern, recent_files)`**: 递归 `rglob`，`fnmatch` 匹配，按 `st_mtime` 降序取前 N 个
- **`search_lines(file_path, keyword, max_lines, tail, line_start, line_end)`**:
  - 有关键字 → 全文件 grep → 行号范围截取匹配结果
  - 无关键字 → 行号范围 → tail/head 截取
- **`scan_logs(folder, root_dirs, ...)`**: 若 folder 指向文件直接读取，否则 `find_files` → 遍历文件 `search_lines`，关键字上限 500 行

### `routes.py` — API 路由
```
LogQueryRequest        → Pydantic 请求模型，field_validator 校验 line_end≥line_start
ConfigUpdateRequest    → TOML 配置内容更新
router                 → APIRouter(), 不含 prefix
```
- 所有异常统一转换为 HTTPException（403/404/500）
- `/api/logs` 支持文件夹/文件两种模式自动切换
- `/api/scan-dirs` 只扫描 `log/` 和 `logs/` 名称的目录（递归）
- `/api/files` 递归遍历白名单目录全部文件，按 mtime 降序
- `/api/logs/self` 从 `POSTLOOK_SELF_LOG` 环境变量或默认路径读取

### `debug_service.py` — 报文调试 Service (v0.4.0)
- **`test_connection(host, port)`**: Ping + TCP 端口探测，先 ping 后 telnet
- **`send_hex_message(hex_str)`**: 连接→发送→接收→断开（一连接一断），后端 500ms 防抖
- **`load_messages()` / `save_messages()`**: 从 `data/messages.toml` 读写报文分组，TOML 格式
- 大小写自动转换：发送前根据 `config/debug.toml` 的 `auto_lowercase`/`auto_uppercase` 处理

### 前端静态文件
- **`index.html`**: 首页六卡片布局（日志查询/配置管理/服务状态/拓扑/报文调试）
- **`logs.html` / `config.html` / `status.html` / `topology.html`**: 各功能页面，顶部导航栏
- **`debug.html`**: 报文调试 SPA（v0.4.0），仿 SSCOM 多字符串面板，三区布局
- **`style.css`**: ~900 行 Mac 风格，CSS 变量驱动暗黑/亮色切换，响应式设计
- **`js/`**: 模块化 JS 文件（common/debug/logs/config/status/topology）
- **`app.js`**: 旧版三面板逻辑（兼容保留）

## 部署架构

### 多平台支持
`deploy.sh` 自动检测操作系统和 Python 版本，按平台走不同安装策略：

| 平台 | Python 策略 | 说明 |
|------|------------|------|
| openEuler 24.03 | 系统 Python 3.11，直接创建 venv | 无需额外操作 |
| CentOS 7 | 预编译包解压 → 源码编译回退 | 系统 Python 2.7 |
| Ubuntu/Debian | 系统 Python（需 >= 3.9） | `apt install python3-venv` |

### 一键部署
```bash
cd Plugin/postlook
sudo bash deploy/deploy.sh
```

### 部署流程
1. `lib/detect.sh`: 检测 OS_ID / Python 版本 / Python ABI (cp39/cp311)
2. `lib/python.sh`: 确保 Python 3.9+ → 系统用 / 调用 `platform/<os>/setup.sh`
3. 创建 venv 虚拟环境
4. `lib/deps.sh`: 按 ABI 选择 `vendor_packages/common/` + `vendor_packages/<abi>/` 离线安装
5. 初始化 `config/env.toml`（从模板）
6. `lib/supervisor.sh`: 生成 Supervisor 配置 → `supervisorctl update` → 启动服务

### deploy.conf 参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `PROJECT_NAME` | `postlook` | 服务名称 |
| `APP_PORT` | `5011` | 监听端口 |
| `SUPERVISOR_USER` | `ymsk` | 运行用户（部署脚本会通过 `setfacl` 自动赋予系统日志读权限） |
| `SUPERVISOR_CONF_DIR` | `/main/server/supervisor` | Supervisor 配置目录 |
| `LOG_DIR` | `/main/log/app` | 日志输出目录 |
| `VENV_DIR` | `venv` | 虚拟环境目录 |
| `VENDOR_DIR` | `deploy/vendor_packages` | 离线包目录 |
| `PYTHON3_PATH` | (空) | 手动指定 Python 路径（留空自动检测） |

### 端口
- **默认端口**: 5011
- **前端页面**: `http://<ip>:5011`
- **Swagger 文档**: `http://<ip>:5011/docs`

## 日志目录白名单配置（常见服务）
见 `skill/rcs_skill/rcslog_skill.md` 和 `skill/fywds_skill.md`

## 关键设计决策
1. **版本号唯一来源**: `app.py` 中 `__version__`，其他模块通过 `from .app import __version__` 引用
2. **配置热更新**: `save_config_toml()` 写文件后立即调用 `reload_config()` 更新全局变量，不需重启
3. **路径安全多层级**: 绝对路径校验 + 相对路径尝试 + resolved 路径白名单检查 + 符号链接跳过
4. **下载扩展名白名单**: `is_allowed_download()` 仅允许日志类扩展名 + 无扩展名系统日志 + core.PID 特殊格式
5. **系统日志权限**: 部署脚本通过 `setfacl` 赋予运行用户读 `/var/log/messages` 等系统日志权限，避免改为 root 运行
6. **多平台部署**: 自动检测 OS (openEuler/CentOS/Ubuntu) → 按平台选 Python 安装策略 → ABI 感知离线包选择 (cp39/cp311)
7. **前端 SPA 无依赖**: 纯原生 JS，不依赖 React/Vue/jQuery，无构建步骤
8. **关键字搜索上限**: 500 行，防大日志 OOM

## 拓扑图 · 技术架构 (v0.10.0~v0.13.0)

### 视图切换

4 种视图一键切换，底层数据统一：

```
LAYOUTS = {
  horizontal:  { engine: 'dagre',  rankDir: 'LR' }   // 横向分层
  vertical:    { engine: 'dagre',  rankDir: 'TB' }   // 纵向分层
  radial:      { engine: 'radial', 手写递归 }        // 360°扇形
  kg:          { engine: 'kg',     D3力仿真 }         // 知识图谱
}
```

### 数据源

| API | 视图 | 数据内容 |
|-----|------|---------|
| `/api/topology-config` | 横向/纵向/放射 | 文件树: root→branch→service |
| `/api/topology-kg` | 图谱 | 知识图谱: server/branch/service/logfile/query/error_query + produces/has_query/belongs_to/runs_on 边 |

### D3 力仿真参数（图谱视图, v0.13.0）

```
d3.forceSimulation(nodes)
  .force('link',    d3.forceLink(edges)   .distance(70)  .strength(0.25))   // 弹簧引力
  .force('charge',  d3.forceManyBody()    .strength(-200))                   // 磁铁斥力
  .force('center',  d3.forceCenter())                                         // 向心力
  .alphaDecay(0.012)    // 慢衰减 → "水面漂浮停缓"效果
  .velocityDecay(0.45)  // 摩擦力

拖拽: grab→固定节点, drag→更新位置+加热(alpha=0.25), free→释放+惯性漂移
```

### 前端依赖（全部本地离线）

| 文件 | 大小 | 用途 |
|------|------|------|
| `cytoscape.min.js` | 358KB | 图形渲染: 样式/选中/缩放/平移 |
| `dagre.min.js` | 278KB | 分层布局: 自动间距/无重叠 |
| `cytoscape-dagre.js` | 13KB | dagre 适配 Cytoscape |
| `d3.v7.min.js` | 274KB | 力仿真: 持续物理模拟 |
| `topology.js` | ~1000行 | 多视图调度 + 布局引擎切换 + 交互 |

### 复用指南

要将拓扑图移植到其他项目：

1. **数据层**: 实现 `build_topology_tree()` 和 `build_knowledge_graph()` 返回 `{nodes[], edges[]}` 格式
2. **后端**: 挂载两个 GET API（`/api/topology-config` + `/api/topology-kg`）
3. **前端**: 复制 `topology.html` + `topology.js` + `style.css` 拓扑部分
4. **依赖**: 复制 `lib/` 下 4 个 JS 文件
5. **调整**: 修改 `LAYOUTS` 对象 + 节点样式 CSS 选择器即可适配

## ds 说
- **v0.13.0 拓扑图**: 4 视图切换（dagre横向/纵向 + 手写放射 + D3力仿真图谱）。D3 仿真参数 alphaDecay=0.012 实现"水面漂浮"停缓效果，拖拽时固定节点+加热仿真(alpha=0.25)产生涟漪扩散。所有前端依赖均在 lib/ 下离线可用。
- **拓扑移植**: 只需实现两个后端 API（返回统一 `{nodes[], edges[]}` 格式）即可复用整个拓扑前端。LAYOUTS 对象定义视图列表，节点样式通过 CSS class 映射。
- vendor_packages 需要 git 跟踪（离线部署必需），已从 .gitignore 中移除
- vendor_packages 按 Python ABI 分层: `common/`（纯Python共享）、`cp39/`、`cp311/`
- 唯一 ABI 专用包为 `pydantic_core`，其他均为 `py3-none-any.whl`
- 新增 Python 版本时，需用 `pip download pydantic_core --python-version X.Y --platform manylinux2014_x86_64 --only-binary=:all:` 下载对应 ABI 包
- config/env.toml 在 .gitignore 中（含敏感路径），deploy.sh 首次自动从模板初始化
- CentOS 7 glibc 2.17 可能与预编译包不兼容，需回退源码编译
- deploy.sh 重构为 lib/ 模块化架构，新增平台只需在 platform/ 下加 setup.sh
- **v0.2.0 新增**: `/api/download` 端点 + 下载扩展名白名单 + `ensure_syslog_access` 自动授权系统日志读权限
- 下载白名单支持 `.log/.out/.txt/.gz/.zip/.hprof/.core/.dmp` 及无扩展名系统日志
- `core.PID` 格式的 Core Dump 也允许下载（纯数字后缀）
- 前端静态文件修改后需强制刷新浏览器（Ctrl+Shift+R 清除缓存）
- 服务状态面板的文件浏览器，点击文件名自动切换到日志查询面板并填入路径
- 配置管理面板的"扫描日志目录"功能，勾选后可一键添加到 TOML 配置的白名单数组
- /api/scan-dirs 只扫 log/logs 两种目录名（不区分大小写），TAL_log/DPL_log 等需要手动添加
- app.js 中的 queryLoading 防抖机制防止短时间重复提交
- 所有接口返回的 line 均为原始行号（1-based）
- 报告文件放入 `report/` 目录，已 gitignore
- **v0.4.0 新增**: 报文调试模块（/debug 页面 + 8 个 API 端点），支持 TCP Client 发送 hex 报文、Ping + Telnet 端口检测、报文分组管理（TOML 热更新）
- 报文调试零新增依赖，全部使用 Python 标准库（socket/subprocess）
- 报文数据文件 `data/messages.toml` 已提交 git 作为初始示例（电梯协议），用户可通过 TOML 编辑模态框热更新
- 连接配置 `config/debug.toml` 在 .gitignore 中，首次从 `config/template/debug.toml` 模板复制
- 发送模式为一连接一断，不保持长连接；前后端均有 500ms 防抖
- 预留 seq/delay_ms 字段于 messages.toml，为后续循环发送做准备

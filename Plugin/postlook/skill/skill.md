# postlook skill

## 项目概述
**postlook** — 轻量、安全的日志 HTTP 查询服务。通过 POST 请求在指定文件夹内按文件名、关键字、行号范围等条件查询日志，支持 Web UI、配置热更新、路径白名单安全机制。

当前版本：v0.2.0

## 技术栈
| 层级 | 选型 | 说明 |
|------|------|------|
| 语言 | Python 3.9+ | 兼容 CentOS 7 源码编译和预编译包 |
| Web 框架 | FastAPI + Uvicorn | 异步高性能 |
| 数据校验 | Pydantic v2 | Request/Response 模型 |
| 配置解析 | tomli (Python <3.11) / tomllib (3.11+) | TOML 格式 |
| 前端 | 原生 HTML/CSS/JS | 无框架依赖，Mac 暗黑风格 SPA |
| 部署 | Supervisor + 离线 pip 包 | 支持 CentOS 7 离线部署 |

## 项目结构
```
Plugin/postlook/
├── src/postlook/               # 源代码
│   ├── app.py                  # FastAPI 入口，版本号 __version__
│   ├── config.py               # 配置加载/热更新/环境变量覆盖
│   ├── routes.py               # 全部 API 路由定义
│   ├── scanner.py              # 文件扫描与内容读取核心
│   └── static/                 # 前端 SPA
│       ├── index.html          # 主页面（三面板布局）
│       ├── style.css           # Mac 风格样式（暗黑/亮色）
│       └── app.js              # 前端交互逻辑
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

### 前端静态文件
- **`index.html`**: 三面板 SPA（日志查询 / 配置管理 / 服务状态），毛玻璃卡片布局
- **`style.css`**: ~900 行 Mac 风格，CSS 变量驱动暗黑/亮色切换，响应式设计
- **`app.js`**: ~430 行，含主题持久化、面板导航、表单防抖、关键字高亮、XSS 防护、扫描目录添加到白名单、文件浏览器点击复制路径

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

## ds 说
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

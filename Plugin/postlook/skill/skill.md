# postlook skill

## 项目概述
**postlook** — 轻量、安全的日志 HTTP 查询服务。通过 POST 请求在指定文件夹内按文件名、关键字、行号范围等条件查询日志，支持 Web UI、配置热更新、路径白名单安全机制。

当前版本：v0.1.0

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
├── deploy/                     # 部署相关
│   ├── deploy.sh               # 一键离线部署脚本
│   ├── deploy.conf             # 部署配置参数
│   ├── vendor_packages/        # 离线 pip 依赖包
│   ├── centos7_rpms/           # CentOS 7 编译 RPM + 预编译包
│   └── README.md               # 部署文档
├── skill/                      # Skill 文件
│   ├── skill.md                # 本文件
│   ├── fywds_skill.md          # FYWDS 服务日志分析
│   └── rcs_skill/
│       └── rcslog_skill.md     # RCS 日志目录白名单
├── test/                       # 测试
│   └── start.md                # 前端设计文档（非测试脚本）
├── doc/
│   └── api/                    # API 文档
├── logs/                       # 日志（.gitignore）
├── plans/                      # 计划（.gitignore）
├── backup/                     # 备份（.gitignore）
└── dev/                        # 调试脚本（.gitignore）
```

## API 接口（全部 8 个端点）

| 方法 | 路径 | 说明 | 响应模型 |
|------|------|------|----------|
| POST | `/api/logs` | 查询日志内容 | `LogQueryResponse` |
| GET | `/api/logs/self` | 查看 postlook 自身日志 | 自定义 JSON |
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

### 一键部署
```bash
cd Plugin/postlook
sudo bash deploy/deploy.sh
```

### 部署流程
1. 自动检测/安装 Python 3.9（系统 → 预编译 → 源码编译）
2. 初始化 `config/env.toml`（从模板）
3. 离线安装 pip 依赖（vendor_packages/）
4. 生成 Supervisor 配置文件
5. 启动服务 → `supervisorctl`

### deploy.conf 参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `PROJECT_NAME` | `postlook` | 服务名称 |
| `APP_PORT` | `5011` | 监听端口 |
| `SUPERVISOR_USER` | `ymsk` | 运行用户 |
| `SUPERVISOR_CONF_DIR` | `/main/server/supervisor` | Supervisor 配置目录 |
| `LOG_DIR` | `/main/log/app` | 日志输出目录 |
| `VENV_DIR` | `venv` | 虚拟环境目录 |
| `VENDOR_DIR` | `deploy/vendor_packages` | 离线包目录 |

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
4. **CentOS 7 兼容**: 自动检测 python3 → 预编译包解压 → 源码编译回退（Python-3.9.20）
5. **前端 SPA 无依赖**: 纯原生 JS，不依赖 React/Vue/jQuery，无构建步骤
6. **关键字搜索上限**: 500 行，防大日志 OOM

## ds 说
- vendor_packages 需要 git 跟踪（离线部署必需），已从 .gitignore 中移除
- config/env.toml 在 .gitignore 中（含敏感路径），deploy.sh 首次自动从模板初始化
- CentOS 7 glibc 2.17 可能与预编译包不兼容，需回退源码编译
- 前端静态文件修改后需强制刷新浏览器（Ctrl+Shift+R 清除缓存）
- 服务状态面板的文件浏览器，点击文件名自动切换到日志查询面板并填入路径
- 配置管理面板的"扫描日志目录"功能，勾选后可一键添加到 TOML 配置的白名单数组
- /api/scan-dirs 只扫 log/logs 两种目录名（不区分大小写），TAL_log/DPL_log 等需要手动添加
- app.js 中的 queryLoading 防抖机制防止短时间重复提交
- 所有接口返回的 line 均为原始行号（1-based）

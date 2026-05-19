
# postlook

轻量、安全的日志 HTTP 查询服务，后期可扩展为实时监控 Web 应用。

## 项目目标

- 通过简单的 POST 请求，在指定文件夹内按文件名、关键字、行数等条件查询日志内容。
- 严格限制每次返回行数（≤100 行），避免大响应。
- 路径白名单机制，防止越权读取任意文件。
- 为后续扩展为 **Web 实时日志监控页面** 保留架构空间（WebSocket/SSE 推送）。

端口默认5011，前端端口可通过5011访问简单查看该模块日志及运行情况，可通过前端web可视化配置该模块配置，配置使用toml格式

前端ui使用现代化简约风格，参考mac主题风格，支持暗黑模式切换，主暗黑模式

## 当前阶段 (v0.1) 已实现功能

### Web 前端
- Mac 风格暗黑主题 UI，支持亮色/暗黑切换
- 日志查询：目录/文件两种模式，行号范围、关键字搜索
- 配置管理：TOML 编辑器，保存后热更新生效
- 服务状态：在线检测 + 白名单目录文件浏览器（点击文件名自动填入查询）

### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/logs` | 查询日志内容 |
| GET | `/api/config` | 获取当前 TOML 配置 |
| POST | `/api/config` | 保存配置（热更新） |
| GET | `/api/files` | 列出白名单目录文件树 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/help` | 接口文档和使用说明 |
| GET | `/docs` | Swagger UI 交互式文档 |

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
- 路径白名单：`config/env.toml` 中配置 `root_dirs`，支持多个目录
- 环境变量 `POSTLOOK_ROOT` 可覆盖白名单（逗号分隔）
- 不跟随符号链接到白名单外
- 非白名单路径返回 403

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
├── config/                    # 配置文件
│   ├── env.toml              # 启用的配置（进.gitignore）
│   ├── old/                  # 备份及老配置文件
│   └── template/             # 配置文件模板
│       └── env.toml
├── deploy/                    # 部署相关
│   ├── deploy.sh             # 一键离线部署脚本
│   ├── deploy.conf           # 部署配置
│   ├── vendor_packages/      # 离线依赖包（进.gitignore）
│   └── README.md             # 部署文档
├── src/postlook/              # 源代码
│   ├── app.py                # FastAPI 应用入口
│   ├── routes.py             # API 路由
│   ├── scanner.py            # 文件扫描与内容读取
│   ├── config.py             # 配置加载（支持热更新）
│   └── static/               # 前端静态文件
│       ├── index.html        # 主页面
│       ├── style.css         # Mac 暗黑风格样式
│       └── app.js            # 前端交互逻辑
├── test/                     # 测试
│   └── start.md              # 前端设计文档
├── doc/api/                  # API 文档
├── logs/                     # 日志（进.gitignore）
├── plans/                    # 计划（进.gitignore）
├── backup/                   # 备份（进.gitignore）
├── dev/                      # 调试（进.gitignore）
└── skill/                    # skill 文件
```

## 开发路线图

### Phase 1：基础查询 ✅
- [x] 实现 `scanner.py`：文件发现、关键字搜索、tail、行号范围
- [x] 实现 `routes.py` 与 Pydantic 模型
- [x] 安全校验与错误处理
- [x] Web 前端（日志查询 + 配置管理 + 服务状态）
- [x] 配置热更新
- [x] Supervisor 离线部署脚本

### Phase 2：增强查询
- [ ] 支持多关键字 AND/OR 搜索
- [ ] 支持正则表达式匹配
- [ ] 支持时间范围过滤
- [ ] 结果分页

### Phase 3：实时监控
- [ ] WebSocket 端点 `/ws` 实时推送新日志行
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

# 查看配置
curl http://localhost:5011/api/config

# 接口帮助
curl http://localhost:5011/api/help
```

## 为什么叫 postlook？

**post** = 通过 POST 请求获取；**look** = 快速看一眼日志。轻巧、直接、RESTful 风格的工具。

---

*欢迎贡献和反馈。*

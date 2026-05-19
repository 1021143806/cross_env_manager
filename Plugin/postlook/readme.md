
# postlook

轻量、安全的日志 HTTP 查询服务，后期可扩展为实时监控 Web 应用。

## 项目目标

- 通过简单的 POST 请求，在指定文件夹内按文件名、关键字、行数等条件查询日志内容。
- 严格限制每次返回行数（≤100 行），避免大响应。
- 路径白名单机制，防止越权读取任意文件。
- 为后续扩展为 **Web 实时日志监控页面** 保留架构空间（WebSocket/SSE 推送）。

端口默认5011，前端端口可通过5011访问简单查看该模块日志及运行情况，可通过前端web可视化配置该模块配置，配置使用toml格式

前端ui使用现代化简约风格，参考mac主题风格，支持暗黑模式切换，主暗黑模式

## 当前阶段 (v0.1) 核心功能

### POST /api/logs
- **输入参数**：
  - `folder` (string)：日志子目录（相对于允许根目录）或绝对路径（需在白名单内）
  - `pattern` (string，默认 `*.log`)：文件名通配符
  - `keyword` (string，可选)：不区分大小写的搜索关键字
  - `lines` (integer，1-100，默认 50)：返回的最大总行数
  - `tail` (bool，默认 true)：无关键字时，true 返回文件尾部行，false 从头开始（有 keyword 时忽略）
  - `recent_files` (integer，1-50，默认 10)：只扫描最近修改的 N 个匹配文件
- **输出 JSON**：
  ```json
  {
    "total_lines": 83,
    "truncated": false,
    "results": [
      {"file": "error.log", "line": 1523, "content": "[ERROR] timeout ..."},
      ...
    ]
  }
  ```
- **安全**：
  - 配置环境变量 `POSTLOOK_ROOT` 为允许访问的根目录，允许多个目录，目录内允许递归允许。
  - 请求的 `folder` 必须解析后在该根目录内，否则返回 403及更详细信息。
  - 不跟随符号链接到根目录外。

## 技术栈

- **语言**：Python 3.10+
- **Web 框架**：FastAPI（异步支持，自带文档，便于后期加 WebSocket）
- **数据校验**：Pydantic
- **服务器**：Uvicorn
- **部署**：单文件或 Docker，初期可裸跑

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
├── src/postlook/              # 源代码
│   ├── __init__.py           # (待创建)
│   ├── app.py                # FastAPI 应用入口 + 静态文件挂载
│   ├── routes.py             # (待创建) POST /api/logs 路由
│   ├── scanner.py            # (待创建) 文件扫描与内容读取逻辑
│   ├── config.py             # (待创建) 配置加载
│   └── static/               # 前端静态文件
│       ├── index.html        # 主页面（左右两栏布局）
│       ├── style.css         # Mac 暗黑风格样式
│       └── app.js            # 前端交互逻辑
├── test/                     # 测试脚本
│   └── start.md              # 前端设计文档
├── doc/                      # 文档
│   └── api/                  # API 文档
├── logs/                     # 日志文件（进.gitignore）
├── plans/                    # 项目计划（进.gitignore）
├── backup/                   # 备份（进.gitignore）
├── dev/                      # 调试脚本（进.gitignore）
└── skill/                    # skill 文件
```

## 开发路线图

### Phase 1：基础查询（当前）
- [ ] 实现 `scanner.py`：文件发现、关键字搜索、tail、总行截断
- [ ] 实现 `routes.py` 与 Pydantic 模型
- [ ] 安全校验与错误处理
- [ ] 单元测试
- [ ] 添加 CLI 方式启动 (`uvicorn src.postlook.app:app`)

### Phase 2：增强查询
- [ ] 支持多关键字 AND/OR 搜索
- [ ] 支持正则表达式匹配
- [ ] 支持时间范围过滤（基于日志行内时间戳）
- [ ] 结果分页（上下翻页）

### Phase 3：实时监控（Web 扩展）
- [ ] 使用 `watchdog` 监听文件夹变更
- [ ] 新增 WebSocket 端点 `/ws`
- [ ] 后端将新日志行实时推送给前端
- [ ] 提供基础 HTML/JS 单页（简单的日志流与统计）

### Phase 4：生产就绪
- [ ] 配置热加载
- [ ] Docker 镜像
- [ ] 访问频率限制与鉴权（API Key / OAuth2）
- [ ] 前端重构为可选的 Vue/React 仪表板

## 快速开始

```bash
# 进入项目目录
cd Plugin/postlook

# 安装依赖
pip install fastapi uvicorn pydantic

# 启动（端口 5011）
python3 -m uvicorn src.postlook.app:app --host 0.0.0.0 --port 5011 --reload
```

启动后访问：
- 前端页面：http://localhost:5011
- API 文档：http://localhost:5011/docs
- 健康检查：http://localhost:5011/api/health

请求示例：
```bash
curl -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{"folder": "2025-05", "pattern": "*.log", "keyword": "error", "lines": 30}'
```

## 为什么叫 postlook？

**post** = 通过 POST 请求获取；**look** = 快速看一眼日志。轻巧、直接、RESTful 风格的工具。

---

*欢迎贡献和反馈。*

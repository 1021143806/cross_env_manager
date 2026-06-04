# postlook API 文档

> 版本: 0.1.0 | 协议: HTTP | 格式: JSON | 端口: 5011

## 目录

1. [POST /api/logs — 查询日志](#1-post-apilogs--查询日志)
2. [GET /api/logs/self — 查看自身日志](#2-get-apilogsself--查看自身日志)
3. [GET /api/config — 获取配置](#3-get-apiconfig--获取配置)
4. [POST /api/config — 保存配置](#4-post-apiconfig--保存配置)
5. [GET /api/scan-dirs — 扫描日志目录](#5-get-apiscan-dirs--扫描日志目录)
6. [GET /api/files — 列出文件树](#6-get-apifiles--列出文件树)
7. [GET /api/health — 健康检查](#7-get-apihealth--健康检查)
8. [GET /api/help — 接口说明](#8-get-apihelp--接口说明)
9. [GET /docs — Swagger UI](#9-get-docs--swagger-ui)
10. [安全机制](#10-安全机制)
11. [错误处理](#11-错误处理)

---

## 1. POST /api/logs — 查询日志

查询日志内容。支持目录模式和文件模式两种方式。

### 请求

```
POST /api/logs
Content-Type: application/json
```

### 请求体 (LogQueryRequest)

| 字段 | 类型 | 必填 | 默认值 | 校验 | 说明 |
|------|------|------|--------|------|------|
| `folder` | string | **是** | - | - | 白名单内的目录路径或文件绝对路径 |
| `pattern` | string | 否 | `"*.log"` | - | 文件名通配符（目录模式下生效） |
| `keyword` | string | 否 | `null` | - | 搜索关键字，不区分大小写 |
| `line_start` | int | 否 | `1` | ≥1 | 起始行号 |
| `line_end` | int | 否 | `100` | ≥line_start | 结束行号（含） |
| `tail` | bool | 否 | `true` | - | 无关键字时从文件尾部读取 |
| `recent_files` | int | 否 | `10` | 1~50 | 扫描最近修改的 N 个文件 |

### 请求示例

```bash
# 目录模式：搜索 /var/log 下 .log 文件最近 10 个文件的前 50 行
curl -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{
    "folder": "/var/log",
    "pattern": "*.log",
    "line_start": 1,
    "line_end": 50
  }'

# 文件模式：直接查看指定文件
curl -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{
    "folder": "/var/log/syslog",
    "line_start": 1,
    "line_end": 100
  }'

# 关键字搜索
curl -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{
    "folder": "/var/log",
    "keyword": "error",
    "line_start": 1,
    "line_end": 500
  }'

# 尾部读取（tail 模式，查看最近日志）
curl -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{
    "folder": "/main/app/ics/logs",
    "pattern": "*.log",
    "tail": true,
    "line_start": 1,
    "line_end": 100,
    "recent_files": 5
  }'
```

### 响应 (LogQueryResponse)

```json
{
  "total_lines": 42,
  "truncated": false,
  "results": [
    {
      "file": "syslog",
      "line": 1234,
      "content": "Jun  4 10:00:00 server kernel: [123456.789] INFO: ..."
    }
  ],
  "keyword": null,
  "error": null
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_lines` | int | 返回的结果行数 |
| `truncated` | bool | 关键字搜索是否超过 500 行上限被截断 |
| `results` | array | 日志行列表，每项含 `file`、`line`(原始行号)、`content` |
| `keyword` | string? | 传入的关键字 |
| `error` | string? | 错误信息（路径不存在等） |

### 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 查询成功（可能返回空结果） |
| 403 | 路径不在白名单内 |
| 404 | 路径不存在或未匹配到文件 |
| 500 | 服务端内部错误 |

---

## 2. GET /api/logs/self — 查看自身日志

查看 postlook 服务自身的日志内容。

### 请求

```
GET /api/logs/self?lines=100&keyword=error
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `lines` | int | 否 | `100` | 返回最近 N 行 |
| `keyword` | string | 否 | - | 过滤关键字，不区分大小写 |

### 请求示例

```bash
curl "http://localhost:5011/api/logs/self?lines=50&keyword=error"
```

### 响应

```json
{
  "total_lines": 3,
  "results": [
    {
      "line": 42,
      "content": "2026-06-04 10:00:00 INFO  postload started port=5011"
    }
  ],
  "log_file": "/main/log/app/postlook.log",
  "log_total_lines": 100
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_lines` | int | 实际返回行数（已过滤） |
| `results` | array | 日志行列表 |
| `log_file` | string | 日志文件路径 |
| `log_total_lines` | int | 日志文件总行数 |

日志路径可通过环境变量 `POSTLOOK_SELF_LOG` 覆盖，默认 `/main/log/app/postlook.log`。

---

## 3. GET /api/config — 获取配置

获取当前 TOML 配置文件原文及解析后的配置值。

### 请求

```
GET /api/config
```

### 请求示例

```bash
curl http://localhost:5011/api/config
```

### 响应

```json
{
  "content": "[server]\nhost = \"0.0.0.0\"\nport = 5011\n\n[logs]\nroot_dirs = [\"/var/log\", \"/main/log/\"]\nmax_lines = 100\ndefault_lines = 50\ndefault_recent_files = 10\n\n[ui]\ntheme = \"dark\"\n",
  "root_dirs": ["/var/log", "/main/log/"],
  "max_lines": 100,
  "default_lines": 50,
  "default_recent_files": 10
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `content` | string | TOML 原文，可直接编辑后回传 |
| `root_dirs` | array | 白名单目录列表（解析后） |
| `max_lines` | int | 最大返回行数 |
| `default_lines` | int | 默认行数 |
| `default_recent_files` | int | 默认最近文件数 |

---

## 4. POST /api/config — 保存配置

保存 TOML 配置内容到文件，并立即热更新生效（无需重启服务）。

### 请求

```
POST /api/config
Content-Type: application/json
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content` | string | **是** | TOML 格式的完整配置内容 |

### 请求示例

```bash
curl -X POST http://localhost:5011/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "content": "[server]\nhost = \"0.0.0.0\"\nport = 5011\n\n[logs]\nroot_dirs = [\"/var/log\", \"/main/app/log\", \"/main/app/ics/logs\"]\nmax_lines = 100\ndefault_lines = 50\ndefault_recent_files = 10\n\n[ui]\ntheme = \"dark\"\n"
  }'
```

### 响应

```json
{
  "status": "ok",
  "message": "配置已保存并热更新生效"
}
```

### 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 配置保存成功 |
| 403 | 无法写入配置文件（权限不足） |
| 500 | 配置内容格式错误或写入失败 |

---

## 5. GET /api/scan-dirs — 扫描日志目录

递归扫描指定路径下名为 `log` 或 `logs`（不区分大小写）的目录。用于在 Web UI 中辅助发现可添加进白名单的日志目录。

### 请求

```
GET /api/scan-dirs?base=/main/app
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `base` | string | 否 | `/main/app` | 扫描的基础路径 |

### 请求示例

```bash
curl "http://localhost:5011/api/scan-dirs?base=/main/app/"
```

### 响应

```json
{
  "base": "/main/app/",
  "exists": true,
  "dirs": [
    {
      "path": "/main/app/ics/logs",
      "file_count": 24,
      "latest_mtime": 1717488000.0
    },
    {
      "path": "/main/app/rtpsa-1/logs",
      "file_count": 156,
      "latest_mtime": 1717487900.0
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `base` | string | 扫描的基础路径 |
| `exists` | bool | 基础路径是否存在 |
| `dirs` | array | 匹配的目录列表 |
| `dirs[].path` | string | 目录绝对路径 |
| `dirs[].file_count` | int | 目录内文件总数 |
| `dirs[].latest_mtime` | float | 目录内最新修改时间戳 |

**注意**: 只扫描名为 `log` 或 `logs` 的目录（不区分大小写）。TAL_log、DPL_log 等非标准命名目录不会被扫描到，需要手动添加。

---

## 6. GET /api/files — 列出文件树

列出所有白名单目录下的文件树，按修改时间降序排列。用于前端"服务状态"面板显示可查看的日志文件。

### 请求

```
GET /api/files
```

### 请求示例

```bash
curl http://localhost:5011/api/files
```

### 响应

```json
{
  "directories": [
    {
      "path": "/var/log",
      "exists": true,
      "files": [
        {
          "name": "syslog",
          "path": "/var/log/syslog",
          "size": 1048576,
          "mtime": 1717488000.0,
          "mtime_str": "2026-06-04 10:00:00"
        }
      ],
      "file_count": 1
    },
    {
      "path": "/main/log",
      "exists": false,
      "files": []
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `directories[].path` | string | 白名单目录路径 |
| `directories[].exists` | bool | 目录是否存在 |
| `directories[].file_count` | int | 文件总数 |
| `directories[].files[]` | array | 文件列表 |
| `files[].name` | string | 文件名 |
| `files[].path` | string | 文件绝对路径 |
| `files[].size` | int | 文件大小（字节） |
| `files[].mtime` | float | 修改时间戳 |
| `files[].mtime_str` | string | 格式化修改时间 |

---

## 7. GET /api/health — 健康检查

快速检查服务是否在线。

### 请求

```
GET /api/health
```

### 请求示例

```bash
curl http://localhost:5011/api/health
```

### 响应

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

## 8. GET /api/help — 接口说明

返回全量的接口文档和使用说明，与当前运行时配置动态绑定（端口、白名单等）。

### 请求

```
GET /api/help
```

### 请求示例

```bash
curl http://localhost:5011/api/help
```

### 响应

返回完整 endpoint 列表、参数说明、curl 示例和当前运行时配置。

---

## 9. GET /docs — Swagger UI

FastAPI 自动生成的 Swagger 交互式 API 文档界面。可通过页面直接在线测试所有接口。

### 请求

```
GET /docs
```

浏览器访问 `http://localhost:5011/docs` 即可使用。

---

## 10. 安全机制

### 路径白名单
所有日志访问路径必须在 `config/env.toml` → `[logs].root_dirs` 配置的目录白名单内。可通过环境变量 `POSTLOOK_ROOT` 覆盖（逗号分隔多个目录）。

### 白名单校验流程
```
用户传入 folder → resolve_folder()
  ├─ 绝对路径 → Path.resolve() → 检查是否在任一 root_dir 下
  ├─ 相对路径 → 依次尝试每个 root_dir 拼接 → 存在即返回
  └─ 都不匹配 → 403 PermissionError
```

### 符号链接保护
`find_files()` 中的 `is_symlink()` 检查跳过符号链接，防止通过符号链接逃逸到白名单外的目录。

### 输出限制
- 关键字搜索上限: 500 行（`MAX_KEYWORD_RESULTS`）
- 单次查询最大返回: 100 行（`MAX_LINES`）
- 最近文件数上限: 50（`MAX_RECENT_FILES`）

### XSS 防护
前端使用 `escapeHtml()` 对日志内容进行 HTML 转义后再插入 DOM。

---

## 11. 错误处理

所有 API 错误统一返回 HTTPException，结构如下：

```json
{
  "detail": "目录 '/etc' 不在允许的白名单内。白名单: ['/var/log']"
}
```

### 错误码速查

| HTTP 状态码 | 典型场景 |
|-------------|----------|
| **403** | 路径不在白名单内、无权限读取 |
| **404** | 路径不存在、未匹配到文件 |
| **422** | 请求体格式错误（Pydantic 校验失败） |
| **500** | 服务端异常、配置文件写入失败 |

### Pydantic 校验错误示例（422）

```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["body", "line_end"],
      "msg": "Input should be greater than or equal to 1",
      "input": 0
    }
  ]
}
```

---

## 配置模板

完整 TOML 配置格式：

```toml
[server]
host = "0.0.0.0"
port = 5011

[logs]
# 允许访问的日志根目录（多个目录用数组）
root_dirs = ["/var/log", "/main/log", "/main/log/app", "/main/app/log"]
# 每次查询最大返回行数
max_lines = 100
# 默认返回行数
default_lines = 50
# 默认扫描最近文件数
default_recent_files = 10

[ui]
# 默认主题: dark | light
theme = "dark"
```

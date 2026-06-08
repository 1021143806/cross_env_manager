# postlook API 实战 skill

## 概述

postlook 提供 9 个 HTTP 端点 + Swagger UI，用于日志查询、配置管理、文件下载和服务诊断。
所有接口返回 JSON（下载端点返回文件流），默认端口 `5011`。

## API 速查

| 方法 | 路径 | 用途 | 频次 |
|------|------|------|------|
| POST | `/api/logs` | 查询日志内容 | 高频 |
| GET | `/api/logs/self` | 查看 postlook 自身日志 | 中频 |
| GET | `/api/config` | 获取当前配置 | 低频 |
| POST | `/api/config` | 保存配置（热更新） | 低频 |
| GET | `/api/scan-dirs` | 扫描 log/logs 目录 | 低频 |
| GET | `/api/files` | 列出白名单文件树 | 低频 |
| GET | `/api/download` | 下载日志文件（安全管控） | 中频 |
| GET | `/api/health` | 健康检查 | 高频（监控） |
| GET | `/api/help` | 接口文档（含运行时配置） | 低频 |
| GET | `/docs` | Swagger UI 交互式文档 | 按需 |

---

## 1. POST /api/logs — 查询日志（核心）

### 参数详解

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `folder` | string | **必填** | 日志目录（相对/绝对）或文件路径 |
| `pattern` | string | `*.log` | 文件名通配符，目录模式生效 |
| `keyword` | string | null | 不区分大小写搜索 |
| `line_start` | int | `1` | 起始行号（≥1） |
| `line_end` | int | `100` | 结束行号（≥line_start） |
| `tail` | bool | `true` | 无关键字时从尾部读取 |
| `recent_files` | int | `10` | 扫描最近 N 个文件（1~50） |

### 两种模式的行为差异

```
                  ┌─ 文件模式 ─────────────────────────────────┐
                  │ folder 指向一个具体文件 → 直接读取该文件    │
                  │ pattern/tail/recent_files 参数被忽略        │
                  └────────────────────────────────────────────┘

                  ┌─ 目录模式 ─────────────────────────────────┐
   POST /api/logs ┤ folder 指向一个目录 → 按 pattern 搜索文件  │
                  │ 按 mtime 降序取 recent_files 个文件         │
                  │ 每个文件按 line_start~line_end 截取         │
                  └────────────────────────────────────────────┘
```

### 关键字搜索特性

- **搜索范围**：对所有匹配文件全量 grep → 再按 `line_start/line_end` 提取匹配结果中的子集
- **上限 500 行**：超过时 `truncated: true`，返回前 500 行
- **循环读取**：多个文件时收集满 500 行即停止扫描后续文件

### 无关键字特性

- **tail=true（默认）**：取文件末尾 N 行（N = line_end - line_start + 1）
- **tail=false**：取文件开头 N 行
- **指定行号范围**：精确截取文件的指定行区间

### curl 实战模板

```bash
# ── 基础查询：查看目录下最近日志 ──
curl -s -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{"folder": "/main/app/fywds/logs", "line_start": 1, "line_end": 50}'

# ── 关键字搜索：查错误 ──
curl -s -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{"folder": "/main/app/ics/logs", "keyword": "ERROR", "line_start": 1, "line_end": 500}'

# ── 文件模式：看单个文件 ──
curl -s -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{"folder": "/main/app/fywds/logs/FYWDS.log", "line_start": 1, "line_end": 100}'

# ── tail 模式：看最新日志 ──
curl -s -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{"folder": "/main/app/tps/logs", "tail": true, "line_start": 1, "line_end": 100, "recent_files": 3}'

# ── 指定通配符 + 更多文件 ──
curl -s -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{"folder": "/main/app/bms/logs", "pattern": "*.out", "recent_files": 5, "line_start": 1, "line_end": 50}'
```

### 响应结构

```json
{
  "total_lines": 42,
  "truncated": false,
  "results": [
    {
      "file": "FYWDS.log",
      "line": 1289,
      "content": "2026-06-08 10:00:00.123 [-] [main] INFO  com.example.Service - started"
    }
  ],
  "keyword": null,
  "error": null
}
```

| 字段 | 说明 |
|------|------|
| `total_lines` | 返回的行数 |
| `truncated` | 关键字搜索是否超过 500 行被截断 |
| `results[].file` | 文件名（不含路径） |
| `results[].line` | 原始行号（1-based） |
| `results[].content` | 行内容，已去除尾随换行 |
| `keyword` | 回传关键字 |
| `error` | 出错时的错误描述 |

---

## 2. 配置管理

### 查看配置

```bash
curl -s http://localhost:5011/api/config | python3 -m json.tool
```

返回内容：
- `content` — TOML 原文，可直接编辑后回传
- `root_dirs` — 白名单目录列表（解析后）
- `max_lines` / `default_lines` / `default_recent_files`

### 热更新配置

```bash
# 将以下 content 的值替换为你需要的 TOML 内容
curl -s -X POST http://localhost:5011/api/config \
  -H "Content-Type: application/json" \
  -d '{"content": "[server]\nhost = \"0.0.0.0\"\nport = 5011\n\n[logs]\nroot_dirs = [\"/var/log\", \"/main/app/ics/logs\", \"/main/app/tps/logs\"]\nmax_lines = 100\ndefault_lines = 50\ndefault_recent_files = 10\n\n[ui]\ntheme = \"dark\"\n"}'
```

成功返回 `{"status": "ok", "message": "配置已保存并热更新生效"}`。

### 热更新机制

```
POST /api/config → save_config_toml()
  ├─ 写文件 config/env.toml
  └─ reload_config() → 重新解析 TOML → 更新全局变量
```

**注意**：热更新仅影响运行时变量（ROOT_DIRS、MAX_LINES 等），不重启进程。
如需重启后仍生效，必须确保 `config/env.toml` 写入成功（热更新本身就会写文件）。

---

## 3. 文件发现

### GET /api/files — 列出白名单文件树

```bash
curl -s http://localhost:5011/api/files | python3 -c "
import sys, json
data = json.load(sys.stdin)
for d in data['directories']:
    print(f\"[{d['path']}] ({d['file_count']} files)\")
    for f in d['files'][:5]:
        print(f\"  {f['mtime_str']} {f['size']:>10}B {f['name']}\")
"
```

适用于前端"服务状态"面板展示。

### GET /api/scan-dirs — 扫描日志目录

```bash
# 扫描 /main/app 下所有 log/logs 目录
curl -s "http://localhost:5011/api/scan-dirs?base=/main/app"

# 扫描具体应用目录
curl -s "http://localhost:5011/api/scan-dirs?base=/main/app/ics"
```

**重要限制**：只扫描名为 `log` 或 `logs`（不区分大小写）的目录。
`TAL_log`、`DPL_log` 等非标准命名不会被扫到，需要手动添加至白名单。

---

## 4. 自身诊断

### 健康检查

```bash
curl -s http://localhost:5011/api/health
# → {"status":"ok","version":"0.1.0"}
```

### 查看 postlook 自身日志

```bash
# 最近 50 行
curl -s "http://localhost:5011/api/logs/self?lines=50"

# 过滤关键字
curl -s "http://localhost:5011/api/logs/self?lines=200&keyword=error"

# 查看全部（无过滤）
curl -s "http://localhost:5011/api/logs/self?lines=99999"
```

日志路径默认 `/main/log/app/postlook.log`，可被环境变量 `POSTLOOK_SELF_LOG` 覆盖。

### 接口文档

```bash
# 动态接口文档（含当前运行时配置）
curl -s http://localhost:5011/api/help | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"postlook v{data['version']}\")
print(f\"端口: {data['base_url']}\")
print(f\"白名单: {data['config']['root_dirs']}\")
print(f\"\\n接口列表:\")
for ep in data['endpoints']:
    print(f\"  {ep['method']:6s} {ep['path']}")
"
```

---

## 5. GET /api/download — 下载日志文件

下载白名单内的日志文件到本地。双重安全管控：路径白名单 + 扩展名白名单。

### 请求

```
GET /api/download?path=/var/log/messages
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | **是** | 文件绝对路径（必须在白名单目录内） |

### 请求示例

```bash
# 下载日志文件
curl -O 'http://localhost:5011/api/download?path=/main/app/gateway/logs/GATEWAY.log'

# 下载压缩日志
curl -o syslog.gz 'http://localhost:5011/api/download?path=/var/log/syslog.1.gz'

# 下载系统日志（无扩展名）
curl -o messages 'http://localhost:5011/api/download?path=/var/log/messages'
```

### 安全管控规则

| 规则 | 说明 | 违规响应 |
|------|------|----------|
| 路径白名单 | 文件必须在 `root_dirs` 内 | 403 |
| 扩展名白名单 | 仅允许日志类扩展名 | 403 |
| 符号链接 | 禁止下载符号链接指向的文件 | 403（扫描阶段跳过） |
| 文件大小上限 | 默认 200MB，可配置，硬上限 1GB | 413 |

### 允许下载的文件类型

| 类别 | 扩展名 | 示例 |
|------|--------|------|
| 标准日志 | `.log` `.out` `.txt` `.dat` | GATEWAY.log, app.out |
| 压缩日志 | `.gz` `.bz2` `.zip` `.tar` `.xz` | syslog.1.gz, logs.zip |
| 日志滚动 | `.0` `.1` ... `.9` `.current` | GATEWAY.log.1, nacos_gc.log.0.current |
| 调试诊断 | `.hprof` `.core` `.dmp` | heapdump.hprof, core.1234, crash.dmp |
| 无扩展名 | (无) | messages, secure, cron, wtmp, sa08 |

### 禁止下载的文件类型

**不在此表中的任何其他类型均禁止**：`.sh`、`.py`、`.toml`、`.yaml`、`.json`、`.conf`、`.ini`、`.jar`、`.so`、`.key`、`.pem`、`.crt` 等脚本/配置/证书/二进制文件一律拒绝。

### 配置下载大小上限

在 `config/env.toml` 的 `[logs]` 节中设置：

```toml
[logs]
max_download_size = 500   # 单位 MB，上限 1024MB（1GB）
```

也可通过 GET/POST `/api/config` 热更新。

### 响应

```
HTTP/1.1 200 OK
Content-Disposition: attachment; filename="GATEWAY.log"
Content-Type: application/octet-stream
Content-Length: 47673506

<文件二进制流>
```

非 200 响应统一返回 JSON 错误描述。

---

## 6. 安全模型详解

### 路径白名单校验流程

```
用户传入 folder ──→ resolve_folder()
  │
  ├─ 绝对路径 ──→ Path.resolve() → 检查 resolved 路径
  │               是否在任一 root_dir 下
  │               ├─ 是 → 返回
  │               └─ 否 → PermissionError(403)
  │
  └─ 相对路径 ──→ 依次拼接每个 root_dir → 检查是否存在
                  ├─ 存在 → 返回
                  └─ 都不存在 → 返回 root_dirs[0]/folder
                                  （后续会报文件不存在 404）
```

### 安全要点

| 机制 | 说明 |
|------|------|
| 符号链接跳过 | `find_files()` 中 `is_symlink()` 检查，防止链式逃逸 |
| 路径逃逸防御 | `resolved.relative_to(root_path)` 校验，`../` 无法逃出 |
| 环境变量覆盖 | `POSTLOOK_ROOT` 可临时覆盖白名单（逗号分隔） |
| 输出限制 | 关键字最多 500 行，单文件最多 100 行（默认） |
| 下载扩展名白名单 | 仅允许 `.log/.out/.txt/.gz` 等日志类扩展名 |
| 下载大小上限 | 默认 200MB，可配置，硬上限 1GB |
| XSS 防护 | 前端 `escapeHtml()` 转义特殊字符 |

---

## 7. 常见查询模式

### 模式一：查特定时间段的日志

```bash
# 先确定文件名和大致行号，再精确查询
curl -s -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{"folder": "/main/app/fywds/logs", "pattern": "FYWDS-2026-06-08.*", "keyword": "2026-06-08 10:00", "line_start": 1, "line_end": 500}'
```

### 模式二：跨文件关键词统计

```bash
# 用 -o 只输出内容行，然后本地统计
curl -s -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{"folder": "/main/app/ics/logs", "keyword": "Exception", "line_start": 1, "line_end": 500}' \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'匹配 {data[\"total_lines\"]} 行, 截断: {data[\"truncated\"]}')
files = {}
for r in data['results']:
    files[r['file']] = files.get(r['file'], 0) + 1
for f, c in sorted(files.items(), key=lambda x: -x[1]):
    print(f'  {f}: {c} 行')
"
```

### 模式三：查看最新错误

```bash
curl -s -X POST http://localhost:5011/api/logs \
  -H "Content-Type: application/json" \
  -d '{"folder": "/main/log/app", "tail": true, "line_start": 1, "line_end": 50, "recent_files": 5}' \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for r in data['results']:
    if 'error' in r['content'].lower() or 'exception' in r['content'].lower():
        print(f\"[{r['file']}:{r['line']}] {r['content']}\")
"
```

### 模式四：跨服务器查日志（多 postlook 实例汇总）

```bash
# 假设有三台服务器各有 postlook 实例
for host in "server1:5011" "server2:5011" "server3:5011"; do
  echo "=== $host ==="
  curl -s -X POST "http://$host/api/logs" \
    -H "Content-Type: application/json" \
    -d '{"folder": "/main/app/ics/logs", "keyword": "error", "line_start": 1, "line_end": 50}'
done
```

---

## 8. 故障排查

### HTTP 状态码速查

| 状态码 | 含义 | 典型原因 |
|--------|------|----------|
| **200** | 成功 | 查询正常（结果可能为空） |
| **403** | 路径禁止 | 目录不在白名单内、符号链接 |
| **404** | 未找到 | 路径不存在、无匹配文件 |
| **422** | 参数错误 | line_end < line_start、line_start ≤ 0 |
| **500** | 服务端错误 | TOML 解析失败、写入权限不足 |

### 常见问题

#### Q: 返回 403 "目录不在白名单内"
```bash
# 先查看当前白名单
curl -s http://localhost:5011/api/config | python3 -c "
import sys, json
print(json.load(sys.stdin)['root_dirs'])
"

# 如果确实需要该目录，通过热更新添加
# 见上方"热更新配置"章节
```

#### Q: 返回 404 "未找到匹配的文件"
```
可能原因：
1. pattern 不匹配（默认只搜 *.log，.out、.txt 等需要指定）
2. 目录路径拼写错误
3. 文件被清理或尚未生成
```

#### Q: 关键字搜索返回 truncated=true
```
说明匹配结果超过 500 行。
解决：缩小时间范围（指定具体的日志文件 pattern）或增加关键字过滤条件。
```

#### Q: 返回空结果但没有错误
```
可能的场景：
1. 关键字搜索但无匹配（total_lines=0, error=null）
2. 文件模式但行号范围超出文件总行数（返回空）
→ 正常行为，不属于错误
```

---

## 9. 快速诊断脚本

保存为 `test/api_quick_test.sh`，一键检查 postlook 服务状态：

```bash
#!/usr/bin/env bash
# postlook 快速健康检查
HOST=${1:-localhost:5011}

echo "=== 1. 健康检查 ==="
curl -sf "$HOST/api/health" && echo "" || echo "✗ 服务不可达"

echo -e "\n=== 2. 配置白名单 ==="
curl -sf "$HOST/api/config" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for p in d['root_dirs']:
    print(f'  {p}')
print(f'  max_lines={d[\"max_lines\"]}')
"

echo -e "\n=== 3. 文件树概况 ==="
curl -sf "$HOST/api/files" | python3 -c "
import sys, json
for d in json.load(sys.stdin)['directories']:
    s = '✓' if d['exists'] else '✗'
    print(f'  [{s}] {d[\"path\"]} ({d[\"file_count\"]} files)')
"

echo -e "\n=== 4. 自检日志（最近5行） ==="
curl -sf "$HOST/api/logs/self?lines=5" | python3 -c "
import sys, json
for r in json.load(sys.stdin)['results']:
    print(f'  [{r[\"line\"]}] {r[\"content\"]}')
"

echo -e "\n=== 5. 测试日志查询 ==="
curl -sf -X POST "$HOST/api/logs" \
  -H "Content-Type: application/json" \
  -d '{"folder": "/var/log", "line_start": 1, "line_end": 5}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'  结果: {d[\"total_lines\"]} 行')
print(f'  错误: {d.get(\"error\", \"无\")}')
" 2>/dev/null || echo "  /var/log 可能无权限，可忽略"
```

---

## 10. 白名单自扩展（排查场景）

排查问题时经常遇到 postlook 白名单受限、无法访问目标日志目录的情况。**可以直接通过 API 热更新白名单，无需重启服务。**

### 限制说明

> **⚠️ 注意：**
> - 热更新只会修改 `config/env.toml`，若该文件因权限无法写入，则更新失败（返回 403）
> - 如果 postlook 进程用户对目标目录本身无读权限，即使加入白名单也无法读取文件内容
> - 热更新只影响运行时配置，supervisor 重启后会重新加载 `config/env.toml`，若文件未被写入则恢复原样

### 方法一：扫描发现 + 批量添加

```bash
# 1. 扫描 /main/app 下所有 log/logs 目录
curl -s "http://<host>:5011/api/scan-dirs?base=/main/app"

# 2. 记下需要添加的目录路径，构造 TOML 配置
# 3. 获取当前配置原文作为基础
curl -s http://<host>:5011/api/config | python3 -m json.tool
```

### 方法二：直接热更新

```bash
curl -s -X POST http://<host>:5011/api/config \
  -H "Content-Type: application/json" \
  -d '{"content": "[server]\nhost = \"0.0.0.0\"\nport = 5011\n\n[logs]\nroot_dirs = [\"/var/log\", \"/main/app/gateway/logs\", \"/main/app/ics/logs\", \"/main/app/tps/logs\", \"/main/app/bms/logs\", \"/main/log/app\", \"/main/app/log\"]\nmax_lines = 100\ndefault_lines = 50\ndefault_recent_files = 10\n\n[ui]\ntheme = \"dark\"\n"}'
```

> **注意**：`content` 字段需要传入完整的 TOML 配置（不是只传 root_dirs），建议先 GET 当前配置，复制 `content` 字段值后修改 `root_dirs` 数组再 POST 回去。

### 一键添加脚本

保存为 `test/hot_add_whitelist.sh`：

```bash
#!/usr/bin/env bash
# postlook 白名单热更新助手
# 用法: ./hot_add_whitelist.sh <host:port> <dir1> [dir2] ...
HOST=${1:-localhost:5011}; shift
NEW_DIRS=("$@")

# 获取当前配置
CONFIG=$(curl -sf "$HOST/api/config" | python3 -c "
import sys, json
d = json.load(sys.stdin)
# 已有白名单 + 新目录
existing = d['root_dirs']
existing += [p for p in '$*'.split() if p not in existing]
# 重新构造 TOML
lines = []
lines.append('[server]')
lines.append(f'host = \"{d.get(\"server_host\", \"0.0.0.0\")}\"')
lines.append(f'port = {d.get(\"server_port\", 5011)}')
lines.append('')
lines.append('[logs]')
lines.append(f'root_dirs = {existing}')
lines.append(f'max_lines = {d.get(\"max_lines\", 100)}')
lines.append(f'default_lines = {d.get(\"default_lines\", 50)}')
lines.append(f'default_recent_files = {d.get(\"default_recent_files\", 10)}')
lines.append('')
lines.append('[ui]')
lines.append(f'theme = \"{d.get(\"default_theme\", \"dark\")}\"')
print('\\n'.join(lines))
")

# 发送热更新
curl -s -X POST "$HOST/api/config" \
  -H "Content-Type: application/json" \
  -d "{\"content\": $(echo "$CONFIG" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}"
```

### 排查流程建议

```
怀疑某目录有日志但访问不了
  │
  ├─ 1. 调用 /api/scan-dirs 扫描发现目标日志目录
  │
  ├─ 2. 通过 GET /api/config 获取当前配置原文
  │
  ├─ 3. 构造新 TOML（追加目标目录到 root_dirs 数组）
  │
  ├─ 4. POST /api/config 热更新白名单
  │
  └─ 5. 重新 POST /api/logs 查询目标日志
```

---

## 11. 与 `/api/help` 的区别

| | `api_skill.md`（本文件） | `/api/help` |
|---|---|---|
| 位置 | 静态文件（skill目录） | 运行时端点 |
| 内容 | 实战指南、模式、排查 | 接口定义 + 当前配置 |
| 更新频率 | 随版本手动更新 | 自动匹配运行时状态 |
| 用途 | 日常参考 | 快速查看当前服务信息 |

---

## ds 说

- **关键字搜索耗时**：对大文件（100MB+）的 grep 会全量读取，可能耗时数秒。建议配合 `recent_files=1` + 具体日期文件使用
- **tail 模式更高效**：无关键字时 tail 模式只读取文件末尾，对超大文件友好
- **line_start/line_end 的不同语义**：有关键字时，这俩参数是匹配**结果的索引范围**（而非原文行号）；无关键字时是原文行号范围。这是最常见的混淆点
- **跨平台 curl 写法**：`-d` 后的 JSON 建议用单引号包裹，避免 shell 变量展开问题。变量展开时用 `jq` 或 `python3 -c` 构造 JSON
- **热更新只写 config/env.toml**：如果是部署脚本改配置，记得热更新或重启；如果手动改文件，需要 POST 热更新或 supervisorctl restart
- **白名单对相对路径的行为**：`folder: "fywds/logs"` 会依次在每个 root_dir 下拼接查找，找到第一个存在的就返回。多个 root_dir 下有同名目录时只返回第一个
- **日志转义**：content 中的控制字符可能导致终端显示异常，建议通过 `python3 -c "print(repr(content))"` 查看原始内容
- **Swagger UI** 访问 `http://host:5011/docs` 可直接在线测试所有接口，适合探索性调试

# 1. 页面路由

### 1.1 主页
```
GET /
```
返回搜索主页 `index.html`。

### 1.2 搜索模板
```
GET /search
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| search_term | string | 否 | 搜索关键词（模糊匹配模板代码和名称） |
| server | string | 否 | 按服务器 IP 过滤 |
| status | string | 否 | 按状态过滤：`1` 启用 / `0` 禁用 |

返回 `template/search.html`（前端渲染，搜索 + 表格 + 详情面板）。

### 1.3 查看模板详情
```
GET /template/<template_id>
```
返回 `template_detail.html`。

### 1.4 编辑模板
```
GET/POST /edit/<template_id>
```

### 1.5 复制模板
```
GET/POST /copy/<template_id>
```
自动生成新 ID 后缀，继承原模板所有配置和子任务。

### 1.6 编辑子任务
```
POST /edit_detail/<detail_id>
```

### 1.7 查询功能主页
```
GET /query
```
返回 `query/unified_home.html`（统一查询页面）。

### 1.8 旧版查询主页
```
GET /query/legacy
```
返回 `query/index_optimized.html`。

### 1.9 任务下发页面
```
GET /addtask
```
返回 `addTask/addtask.html`。

### 1.10 任务下发帮助
```
GET /addtask/help
```
返回 Markdown 渲染帮助文档。

### 1.11 配置管理页面
```
GET /config
```
返回 `addTask/config_editor.html`。

### 1.12 下发配置查看
```
GET /addtask/config-view
```
返回 `addTask/config_editor_v2.html`（新版统一入口）。

### 1.13 文档页面
```
GET /docs
```
返回 README.md 渲染 HTML。

### 1.14 统计页面
```
GET /stats
```

### 1.15 任务查询主页（1.3 兼容）
```
GET /task_query
```

### 1.16 任务单号查询结果
```
GET /task_query/result
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| order_id | string | 是 | 任务单号 |
| server_ip | string | 否 | 服务器 IP |

### 1.17 跨环境任务模板查询
```
GET /task_query/cross_task_by_template
```

### 1.18 跨环境任务模板详情
```
GET /task_query/cross_model_process_info
```

### 1.19 跨环境任务详情
```
GET /task_query/cross_task_info
```

### 1.20 Join QR Node 列表
```
GET /pair/list
```
返回 `join_qr_nodes/list.html`。

### 1.21 Join QR Node 编辑
```
GET/POST /pair/edit
```

### 1.22 调车看板
```
GET /dispatch
```

### 1.23 调车配置
```
GET /dispatch/config
```

### 1.24 系统配置
```
GET /system/config
```

### 1.25 系统监控
```
GET /monitor
```

### 1.26 数据统计
```
GET /stats
```

### 1.27 平台切换
```
GET /platform-switch
```

### 1.28 升级管理
```
GET /system/upgrade
```
返回 `system/upgrade.html`（升级管理页面，仅 admin 可见）。

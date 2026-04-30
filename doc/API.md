# 跨环境任务模板管理系统 - API 接口文档

> 版本: 1.2 | 最后更新: 2026-04-27 | 基础路径: `http://{host}:5000`

---

## 目录

1. [页面路由](#1-页面路由)
2. [模板管理 API](#2-模板管理-api)
3. [任务查询 API](#3-任务查询-api)
4. [任务重发 API](#4-任务重发-api)
5. [统计 API](#5-统计-api)
6. [Join QR Node API](#6-join-qr-node-api)
7. [配置管理 API](#7-配置管理-api)
8. [认证 API](#8-认证-api)
9. [系统 API](#9-系统-api)

---

## 1. 页面路由

### 1.1 主页
```
GET /
```
返回搜索主页 `index.html`。

### 1.2 搜索模板
```
GET/POST /search
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| search_term | string | 是 | 搜索关键词（模糊匹配模板代码和名称） |

返回 `search_results.html`，展示匹配的模板列表及子任务。

### 1.3 查看模板详情
```
GET /template/<template_id>
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| template_id | int | 是 | 模板ID（路径参数） |

返回 `template_detail.html`。

### 1.4 编辑模板
```
GET/POST /edit/<template_id>
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| template_id | int | 是 | 模板ID（路径参数） |
| model_process_name | string | POST | 模板名称 |
| enable | int | POST | 是否启用 (0/1) |
| request_url | string | POST | 回调URL |
| capacity | int | POST | 容量管控值 |

### 1.5 复制模板
```
GET/POST /copy/<template_id>
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| template_id | int | 是 | 源模板ID |
| new_base_name | string | POST | 新模板基础名称（不含ID后缀） |

自动生成新ID后缀，继承原模板所有配置和子任务。

### 1.6 编辑子任务
```
POST /edit_detail/<detail_id>
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| detail_id | int | 是 | 子任务ID（路径参数） |
| task_seq | int | POST | 任务顺序 |
| template_code | string | POST | 子任务模板代码 |
| template_name | string | POST | 子任务名称 |
| task_servicec | string | POST | 服务器地址 |
| task_path | string | POST | 目标点标识 |

### 1.7 查询功能主页
```
GET /query
```
返回 `query/unified_home.html`（统一查询页面）。

### 1.8 旧版查询主页
```
GET /query/legacy
```
返回 `query/index_optimized.html`（兼容旧版）。

### 1.9 任务下发页面
```
GET /addtask
```
返回 `addTask/addtask.html`。

### 1.10 任务下发帮助文档
```
GET /addtask/help
```
返回 Markdown 渲染的帮助文档 HTML。

### 1.11 配置管理页面
```
GET /config
```
返回 `addTask/config_editor.html`。

### 1.12 文档页面
```
GET /docs
```
返回 `README.md` 渲染后的 HTML。

### 1.13 统计页面
```
GET /stats
```
返回 `stats.html`。

### 1.14 任务查询主页（1.3兼容）
```
GET /task_query
```
返回 `query/task_query_home.html`。

### 1.15 任务单号查询结果
```
GET /task_query/result
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| order_id | string | 是 | 任务单号 |
| server_ip | string | 否 | 服务器IP（支持简写如"32"） |

### 1.16 跨环境任务模板查询
```
GET /task_query/cross_task_by_template
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| template_code | string | 是 | 跨环境模板代码 |

### 1.17 跨环境任务模板详情
```
GET /task_query/cross_model_process_info
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| template_code | string | 是 | 跨环境模板代码 |

### 1.18 跨环境任务详情
```
GET /task_query/cross_task_info
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| order_id | string | 是 | 跨环境任务编号 |

### 1.19 Join QR Node 列表
```
GET /join_qr_nodes
```
返回 `join_qr_nodes.html`。

### 1.20 Join QR Node 搜索
```
GET /join_qr_nodes/search
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| search_term | string | 是 | 搜索关键词 |

返回 JSON。

### 1.21 Join QR Node 详情
```
GET /join_qr_nodes/<node_id>
```

### 1.22 Join QR Node 编辑
```
GET/POST /join_qr_nodes/<node_id>/edit
```

### 1.23 Join QR Node 添加
```
GET/POST /join_qr_nodes/add
```

---

## 2. 模板管理 API

### 2.1 搜索建议
```
GET /api/search_suggestions
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| term | string | 是 | 搜索关键词 |

**响应示例:**
```json
[
  {
    "code": "HJBY_back_32A3DJ2F_to_31A3QD4B3F_446",
    "name": "回流_32A3DJ2F_to_31A3QD4B3F_446"
  }
]
```

### 2.2 添加子任务
```
POST /api/template/<template_id>/details/add
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| template_id | int | 是 | 模板ID（路径参数） |
| task_seq | int | 是 | 任务顺序 |
| template_code | string | 是 | 子任务模板代码 |
| template_name | string | 是 | 子任务名称 |
| task_servicec | string | 是 | 服务器地址 |
| task_path | string | 否 | 目标点标识 |

**响应示例:**
```json
{
  "success": true,
  "message": "子任务添加成功",
  "detail_id": 123
}
```

### 2.3 删除子任务
```
DELETE /api/template/<template_id>/details/<detail_id>/delete
```
**响应示例:**
```json
{
  "success": true,
  "message": "子任务删除成功"
}
```

### 2.4 子任务排序
```
POST /api/template/<template_id>/details/reorder
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| template_id | int | 是 | 模板ID（路径参数） |
| order | array | 是 | 子任务ID数组（按新顺序排列） |

**请求体示例:**
```json
{
  "order": [101, 103, 102]
}
```

---

## 3. 任务查询 API

### 3.1 获取任务组信息
```
GET /api/task_group/<order_id>
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| order_id | string | 是 | 任务单号（路径参数） |
| server_ip | string | 否 | 服务器IP（查询参数） |

**响应示例:**
```json
{
  "success": true,
  "taskGroup": {
    "id": 6413848,
    "third_order_id": "1777011009",
    "status": 8,
    "robot_id": "BE04253BAK00001",
    "device_ip": "10.68.2.32",
    "shelf_model_name": "标准货架",
    "task_status_name": "已完成"
  },
  "details": [
    {
      "id": 123,
      "tg_id": 6413848,
      "task_seq": 1,
      "status": 8,
      "device_ip": "10.68.2.32"
    }
  ],
  "source": "local"
}
```

---

## 4. 任务重发 API

### 4.1 重发跨环境任务
```
POST /api/task/resend
```
> ⚠️ 此接口直接修改生产数据库，请谨慎使用。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| orderId | string | 是 | 大模板任务单号 |
| subOrderId | string | 是 | 子任务ID（当前） |
| taskSeq | int | 是 | 子任务序号 |
| serverIp | string | 否 | 数据库服务器IP（默认 10.68.2.32） |

**请求体示例:**
```json
{
  "orderId": "1.7771976967327742E12",
  "subOrderId": "1.7771976967327742E12_2_5450",
  "taskSeq": 2
}
```

**成功响应:**
```json
{
  "success": true,
  "newSubOrderId": "1.7771976967327742E12_2_5451",
  "message": "重发成功，新子任务ID: 1.7771976967327742E12_2_5451，3秒后将自动刷新"
}
```

**前置任务检查失败:**
```json
{
  "success": false,
  "code": "PRECEDING_TASK_ACTIVE",
  "precedingTaskId": "1.7771976967327742E12_1_5449",
  "serverUrl": "http://10.68.2.32:7000",
  "message": "上一条任务（task_seq=1）仍在执行中（status=6），请先到对应服务器查询或取消该任务后再重发"
}
```

**多执行中任务异常:**
```json
{
  "success": false,
  "code": "MULTIPLE_ACTIVE",
  "message": "该异常任务可能与跨环境模块负荷异常或重启导致，反馈研发后可使用该功能进行恢复。当前有 2 个执行中的子任务",
  "activeTasks": [
    {"sub_order_id": "xxx_1_100", "task_seq": 1, "status": 6, "service_url": "http://10.68.2.32:7000"},
    {"sub_order_id": "xxx_2_200", "task_seq": 2, "status": 6, "service_url": "http://10.68.2.32:7000"}
  ]
}
```

**状态不允许重发:**
```json
{
  "success": false,
  "code": "INVALID_STATUS",
  "message": "大模板状态不允许重发（当前状态: 8）"
}
```

**重发逻辑说明:**

| 大模板状态 | 子模板状态 | 行为 |
|-----------|-----------|------|
| 3（已取消） | 3（已取消） | 大模板改为5，子模板改为5，sub_order_id+1 |
| 5（重发中） | 7（失败） | 仅子模板改为5，sub_order_id+1 |
| 7（任务失败） | 7（失败） | 仅子模板改为5，sub_order_id+1 |
| 6/9（已下发） | 4/6/9 | 大模板改为5，子模板改为5，sub_order_id+1 |

---

## 5. 统计 API

### 5.1 系统概览统计
```
GET /api/stats/overview
```
**响应示例:**
```json
{
  "success": true,
  "total_templates": 150,
  "enabled_templates": 120,
  "total_details": 450,
  "avg_details_per_template": 3.0
}
```

### 5.2 模板分布统计
```
GET /api/stats/distribution
```

### 5.3 按服务器统计模板
```
GET /api/stats/templates_by_server
```

### 5.4 模板增长趋势
```
GET /api/stats/template_growth
```

### 5.5 详细分析
```
GET /api/stats/detailed_analysis
```

---

## 6. Join QR Node API

### 6.1 删除节点
```
DELETE /api/join_qr_nodes/<node_id>/delete
```
**响应示例:**
```json
{
  "success": true,
  "message": "记录删除成功"
}
```

### 6.2 节点统计
```
GET /api/join_qr_nodes/stats
```

---

## 7. 配置管理 API

### 7.1 获取配置
```
GET /addtask/config
```
返回 `config.js` 文件内容（text/plain）。

### 7.2 保存配置
```
POST /addtask/config
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content | string | 是 | 配置文件内容 |
| message | string | 否 | 提交消息（用于版本记录） |

### 7.3 备份列表
```
GET /addtask/config/backups
```

### 7.4 创建备份
```
POST /addtask/config/backup
```

### 7.5 获取备份内容
```
GET /addtask/config/backup/<backup_name>
```

### 7.6 恢复备份
```
POST /addtask/config/backup/<backup_name>/restore
```

### 7.7 删除备份
```
DELETE /addtask/config/backup/<backup_name>
```

---

## 8. 认证 API

### 8.1 登录
```
POST /api/login
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

**响应示例:**
```json
{
  "success": true,
  "message": "登录成功",
  "username": "admin"
}
```

### 8.2 注销
```
POST /api/logout
```
**响应示例:**
```json
{
  "success": true,
  "message": "已注销"
}
```

### 8.3 认证状态
```
GET /api/auth/status
```
**响应示例:**
```json
{
  "logged_in": true,
  "username": "admin",
  "login_time": "2026-04-27T10:00:00"
}
```

---

## 9. 系统 API

### 9.1 健康检查
```
GET /actuator/health
```
**响应:**
```
1000
```
返回纯文本 `1000`，用于服务器监控。

### 9.2 版本树测试
```
GET /test/version_tree
```
返回 `test_version_tree.html`（测试用）。

---

## 附录

### 状态码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 404 | 资源未找到 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用（模块未加载） |

### 通用错误响应格式

```json
{
  "success": false,
  "code": "ERROR_CODE",
  "message": "错误描述信息"
}
```

### 数据库表说明

| 表名 | 说明 |
|------|------|
| fy_cross_model_process | 跨环境任务模板主表 |
| fy_cross_model_process_detail | 跨环境子任务模板明细表 |
| fy_cross_task | 跨环境任务主表（大模板） |
| fy_cross_task_detail | 跨环境任务子表（子模板） |
| task_group | 本地任务组表 |
| task_group_detail | 本地任务组明细表 |
| join_qr_node_info | QR节点信息表 |
| agv_robot | AGV设备表 |
| load_config | 货架配置表 |
| task_status_config | 任务状态配置表 |

### 4.2 异常完成（仅将子任务状态置为3）
```
POST /api/task/force_complete
```
> 仅修改子模板状态为3（已取消），不修改大模板和sub_order_id。适用于重发中（status=5）卡住的子任务。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| orderId | string | 是 | 大模板任务单号 |
| subOrderId | string | 是 | 子任务ID |
| taskSeq | int | 是 | 子任务序号 |
| serverIp | string | 否 | 数据库服务器IP（默认 10.68.2.32） |

**请求体示例:**
```json
{
  "orderId": "1.7771976967327742E12",
  "subOrderId": "1.7771976967327742E12_2_5450",
  "taskSeq": 2
}
```

**成功响应:**
```json
{
  "success": true,
  "message": "异常完成成功，子任务 1.7771976967327742E12_2_5450 状态已改为3（已取消），3秒后将自动刷新"
}
```

**状态不允许:**
```json
{
  "success": false,
  "code": "INVALID_STATUS",
  "message": "仅允许对重发中（status=5）的子任务执行异常完成操作（当前状态: 7）"
}
```

### 5.6 大模板状态分布统计（含error_desc细分）
```
GET /api/stats/main_task_status
```
查询当天 `fy_cross_task` 表按 `task_status` 分组统计，异常状态（3,7）额外按 `error_desc` 细分。

**响应示例:**
```json
{
  "success": true,
  "total": 150,
  "date": "2026-04-27",
  "distribution": [
    {"status": -1, "label": "容量管控", "color": "#6c757d", "count": 5, "subs": []},
    {"status": 3, "label": "已被异常完成", "color": "#ffc107", "count": 12, "subs": ["请勿频繁请求", "任务异常结束", "小车预占失败", "请勿重复下发任务", "已下发"]},
    {"status": 5, "label": "重发中", "color": "#fd7e14", "count": 3, "subs": ["请勿频繁请求"]},
    {"status": 6, "label": "已下发", "color": "#0d6efd", "count": 25, "subs": []},
    {"status": 7, "label": "任务失败", "color": "#dc3545", "count": 8, "subs": ["货架未初始化(7301)", "找不到任务模板", "车没有预占(7027)", "action条件判断错误(0X2032)"]},
    {"status": 8, "label": "任务完成", "color": "#198754", "count": 97, "subs": []}
  ],
  "errorDetail": [
    {"status": 3, "errorDesc": "请勿频繁请求", "count": 5},
    {"status": 3, "errorDesc": "任务异常结束", "count": 3},
    {"status": 7, "errorDesc": "货架未初始化(7301)", "count": 4},
    {"status": 7, "errorDesc": "找不到任务模板", "count": 2}
  ]
}
```

# 2. 模板管理 API

### 2.1 分页搜索
```
GET /api/search
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| q | string | 否 | 搜索关键词 |
| page | int | 否 | 页码，默认 1 |
| per_page | int | 否 | 每页条数，默认 20 |
| server | string | 否 | 按服务器 IP 过滤 |
| status | string | 否 | 按状态过滤 |
| sort_by | string | 否 | 排序字段 |
| sort_order | string | 否 | ASC / DESC |

**响应示例:**
```json
{
  "success": true,
  "data": {
    "templates": [
      {
        "id": 1,
        "model_process_code": "HJBY_back...",
        "model_process_name": "回流",
        "target_points_ip": "10.68.2.32",
        "enable": 1,
        "area_id": 1,
        "capacity": 10,
        "detail_count": 3
      }
    ],
    "total": 42,
    "page": 1,
    "per_page": 20,
    "total_pages": 3,
    "servers": ["10.68.2.31", "10.68.2.32"]
  }
}
```

### 2.2 搜索建议
```
GET /api/search_suggestions
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| term | string | 是 | 搜索关键词 |

### 2.3 获取模板详情
```
GET /api/template/<template_id>
```

### 2.4 添加子任务
```
POST /api/template/<template_id>/details/add
```

### 2.5 删除子任务
```
DELETE /api/template/<template_id>/details/<detail_id>/delete
```

### 2.6 子任务排序
```
POST /api/template/<template_id>/details/reorder
```

### 2.7 交接点检查
```
GET /api/template/<id>/join_qr_check
```
逐个检查每个子任务服务器的 `join_qr_node_info` 配置状态。

### 2.8 设备同步
```
POST /api/template/device-sync
```
SSE 流式推送实时日志。

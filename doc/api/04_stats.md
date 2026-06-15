# 4. 统计 API

### 4.1 系统概览统计
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

### 4.2 模板分布统计
```
GET /api/stats/distribution
```

### 4.3 按服务器统计模板
```
GET /api/stats/templates_by_server
```

### 4.4 模板增长趋势
```
GET /api/stats/template_growth
```

### 4.5 详细分析
```
GET /api/stats/detailed_analysis
```

### 4.6 大模板状态分布（含 error_desc 细分）
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
    {"status": 6, "label": "已下发", "color": "#0d6efd", "count": 25, "subs": []},
    {"status": 8, "label": "任务完成", "color": "#198754", "count": 97, "subs": []}
  ],
  "errorDetail": [
    {"status": 3, "errorDesc": "请勿频繁请求", "count": 5}
  ]
}
```

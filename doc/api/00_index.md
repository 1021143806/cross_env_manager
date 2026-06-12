# 跨环境任务模板管理系统 - API 接口文档

> 版本: 1.4 | 最后更新: 2026-06-12 | 基础路径: `http://{host}:5000`

## 模块索引

| # | 模块 | 文件 | 说明 |
|---|------|------|------|
| 1 | [页面路由](01_page_routes.md) | `routes/template_routes.py`、`routes/task_routes.py` 等 | 所有页面 URL |
| 2 | [模板管理](02_template.md) | `routes/template_routes.py` | 模板 CRUD、子任务管理 |
| 3 | [任务查询 & 重发](03_task.md) | `routes/task_routes.py`、`app.py` | 任务组查询、重发、异常完成 |
| 4 | [统计](04_stats.md) | `routes/stats_routes.py` | 系统概览、分布、趋势 |
| 5 | [交接点配置](05_join_qr.md) | `routes/join_qr_routes.py` | QR 节点管理、配对 |
| 6 | [配置管理](06_config.md) | `routes/config_routes.py` | 调度配置、备份 |
| 7 | [认证](07_auth.md) | `routes/auth_routes.py` | 登录、注销、状态 |
| 8 | [系统](08_system.md) | `routes/system_routes.py`、`routes/system_upgrade_routes.py` | 健康检查、升级管理 |
| 9 | [定制表编辑](09_custom_table.md) | `routes/custom_table_routes.py` | 跨库表编辑 |

---

## 附录

### 状态码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 403 | 需要管理员权限 |
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
| join_qr_node_info | QR 节点信息表 |
| agv_robot | AGV 设备表 |
| load_config | 货架配置表 |
| task_status_config | 任务状态配置表 |
| bms_user | 用户表（认证用） |

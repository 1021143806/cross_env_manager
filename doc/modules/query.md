# 查询模块

> 最后更新: 2026-06-02 | 路由: `routes/task_routes.py` | 版本: `TASK_VERSION`

---

## 一、功能

- **统一查询页面** (`/query`): 任务单号、货架号、设备号三种查询模式
- **旧版查询** (`/query/legacy`): 兼容旧版页面
- **1.3 任务查询** (`/task_query`): 深度查询（跨环境任务分析）

## 二、查询模式

| 模式 | 入口 | 查询方式 |
|------|------|---------|
| 任务单号 | 输入 orderId | `GET /api/task_group/<orderId>` → 本地数据库 + ICS 远程 |
| 货架号 | 输入 shelfNum | 本地数据库 + ICS 远程 |
| 设备号 | 输入 deviceNum | 本地数据库 + ICS 远程（3 次重试） |

## 三、查询代理

`POST /addtask/query` 作为统一代理：

```
浏览器 → Flask → ICS 服务器 (10.68.2.32:7000 / 8315)
         ↑
    浏览器不直接暴露服务器 IP
```

## 四、任务重发

| API | 说明 |
|-----|------|
| `POST /api/task/resend` | 修改大模板状态 → sub_order_id+1 → 调用 ICS |
| `POST /api/task/force_complete` | 仅修改子模板状态为 3（取消），不修改 sub_order_id |

## 五、跨环境任务浏览 (v2.4.7+)

**页面**: `/query/cross-tasks` 直接查询 `fy_cross_task` 表

**筛选参数**（11个）：orderId、task_status（气泡多选）、device_num、shelf_num、from_system（气泡多选）、create_time、model_process_code、model_process_name、task_error（气泡多选）、device_code、taskPath

**API**:
| 端点 | 说明 |
|------|------|
| `GET /query/cross-tasks` | 页面渲染 |
| `POST /api/query/cross_tasks` | 分页查询，支持数组 IN 筛选，每页 20-200 条可调，最多 2 页 |
| `GET /api/query/cross_task_filters` | 返回 from_system/task_status/task_error 的下拉选项（含 count，5分钟缓存） |

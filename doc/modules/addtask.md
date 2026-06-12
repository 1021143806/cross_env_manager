# 任务下发模块 (AddTask)

> 最后更新: 2026-06-12 | 路由: `app.py` (代理查询) | 前端: `static/js/addtask.js` | 版本: v1.7.0

---

## 一、功能

- **任务下发页面** (`/addtask`): 按区域/楼栋分组选择任务模板，下发 AGV 任务
- **下发配置** (`/addtask/config-view`): 编辑 `dispatch_config.json`（新版统一入口）
- **已发查询** (`/addtask` 右侧面板): 按订单号/货架号/设备号查询任务状态

## 二、核心功能

### 2.1 任务分组

| 分组 | 说明 |
|------|------|
| ⏏️ 辊筒任务 | 非跨环境、不带货架，固定下发点位 |
| 🚛 回空车 | 返回空车任务 |
| 📦 非空车 | 带货架的任务 |

每个选项显示 `模板名称 [当前/容量]`，达到容量上限时自动禁用。

### 2.2 辊筒任务

- 配置字段：`roller_task: true` + `roller_point` + `roller_point_label`
- 全局开关：`dispatch_config.json._features.enable_roller_task`
- OrderId 前缀：`RLLR_`
- 下发后 orderId 缓存到 `localStorage`，15 秒轮询状态
- 状态 8 自动释放容量

### 2.3 查询路由

| orderId 前缀 | 查询 API |
|-------------|---------|
| `RLLR_` | `POST {ip}:7000/ics/out/task/getTaskOrderStatus` |
| `CEM_` | 先 `:8315/crossTask/query`，未找到回退辊筒 API |

### 2.4 容量管控

| 层级 | 配置 | 说明 |
|------|------|------|
| 任务级 | `capacity > 0` | 该任务最大并发数 |
| 辊筒级 | `localStorage['roller_sent_orders']` | 已下发未完成的辊筒任务数 |

## 三、已下发缓存

| Key | 格式 | 说明 |
|-----|------|------|
| `area_usage` | `{area: count}` | 今日各区域使用次数 |
| `task_usage` | `{area_task: count}` | 今日各任务使用次数 |
| `query_history` | 数组 | 最近 5 条查询记录 |
| `roller_sent_orders` | `[{orderId, point, timestamp}]` | 已下发辊筒订单 |

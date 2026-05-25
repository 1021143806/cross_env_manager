---
name: query-page-skill
description: cross_env_manager 深度查询页面（unified_home.html）开发维护指导
---

# 深度查询页面 Skill

## 页面概述

- **路径**: `/task_query` → `templates/query/unified_home.html`
- **后端 API**: `routes/task_routes.py` → `api_device_tasks()`、`api_query_log()`
- **功能**: 任务单号查询、货架查询、设备号深度查询（跨环境任务分析）

## 页面布局

```
┌─ 左侧栏 ────────────────────────┐  ┌─ 右侧结果区 ──────────────────────────┐
│ 查询条件（任务单号/货架/设备号）   │  │ 设备实时状态卡片（设备查询时）           │
│ 本地数据库信息                    │  │ 任务总览卡片                          │
│ 今日任务状态概览（饼图）           │  │ 子任务明细（子任务1、2、3...）          │
│ 最近查询                         │  │ 同模板其他任务                        │
│ 操作日志面板                     │  │                                      │
└─────────────────────────────────┘  └───────────────────────────────────────┘
```

## 核心函数

### 前端 JS（unified_home.html）

| 函数 | 用途 |
|------|------|
| `executeQuery()` | 查询主入口，根据查询类型分发 |
| `renderResult(result)` | 渲染完整查询结果 |
| `renderDeviceStatusCard(result)` | 渲染设备实时状态卡片（卡片式服务器面板） |
| `renderSubTaskCard(task, index, baseUrl, deviceStatuses)` | 渲染单个子任务卡片 |
| `renderDeviceIconForQuery(d, threshold, clickHandler)` | 渲染设备图标（sprite + 电池指示器） |
| `getDeviceSpriteClass(state, battery)` | 根据设备状态返回 sprite 颜色类名 |
| `getDeviceStateClass(state)` | 返回 agv-icon 背景色类名 |
| `getStateBadgeClass(state)` | 返回 badge 颜色类名 |
| `getDeviceStateLabel(state)` | 返回中文状态标签 |
| `fillHistory(term)` | 点击最近查询历史，填入对应输入框并执行查询 |
| `loadQueryLog()` | 定时拉取操作日志 |
| `renderQueryDebugPanel()` | 渲染全链路调试面板 |

### 后端 API（routes/task_routes.py）

| 路由 | 用途 |
|------|------|
| `POST /api/query/device_tasks` | 设备号深度查询（4步链路，返回 recent_tasks + 第一条深度结果） |
| `POST /api/query/device_task_detail` | 按 orderId 获取深度查询结果（设备号查询切换任务时使用） |
| `POST /api/query/order_tasks` | 按 orderId 查询任务详情 + 设备实时状态（任务单号查询） |
| `GET /api/query/log` | 获取操作日志 |
| `GET /api/task_group/<order_id>` | 获取本地 task_group 数据 |
| `GET /api/task/local_detail/<order_id>` | 获取本地 fy_cross_task 详情 |
| `POST /api/task/resend` | 任务重发（先调远端取消接口，再修改数据库状态） |

## 设备状态图标系统

### Sprite 图
- **文件**: `static/img/agv/rcsagv_lift.png`（640×64，10个64×64图标）
- **来源**: 从 `rcsagv.png` 第6行裁剪（举升AGV）
- **CSS 类**: `.agv-sprite`（64×64）、`.agv-sprite-sm`（24×24）

### 颜色映射（按 rcsagvpng.md 第8节）

| col | CSS类 | 颜色 | 设备状态 |
|-----|-------|------|----------|
| 0 | `blue` | 蓝 | Idle（空闲）、InTask（任务中） |
| 1 | `green` | 绿 | Charging（充电中） |
| 2 | `red` | 红 | Error（异常） |
| 3 | `orange` | 橙 | 故障 |
| 4 | `gray` | 灰 | Offline/Downlined（离线/下线） |
| 5 | `purple` | 紫 | 低电量（≤30%，非离线/异常） |

### Badge 颜色

| 状态 | Badge 类 | 颜色 |
|------|----------|------|
| Idle | `success` | 绿 |
| InTask | `primary` | 蓝 |
| Charging | `warning` | 黄 |
| Error | `danger` | 红 |
| Offline/Downlined | `secondary` | 灰 |

## 设备状态卡片（方案A：卡片式服务器面板）

- 标题栏显示设备号：`设备实时状态 · DJC2`
- 大图标（80px容器）+ 网格化核心指标（序列号/状态/电量进度条/区域）
- 服务器结果用独立卡片展示，左侧彩色边框
- `firstOk` 选取逻辑：排除 Offline/Downlined/查询失败，取第一个有效状态，没有则取第一个

## 子任务设备图标

- 每个子任务标题栏显示 24×24 小图标（`agv-sprite-sm`）
- 通过 `serverIp` 匹配 `deviceStatuses` 中的设备状态
- 数据来源：`renderResult` → `result.deviceStatuses` → `renderSubTaskCard` 第4参数

## 最近查询历史

- 存储到 `localStorage`（key: `taskQueryHistory`），最多5条
- `fillHistory` 支持三种后缀：`(设备)` → 设备查询、`(货架)` → 货架查询、纯文本 → 任务单号查询

## 操作日志

- 后端写入：`write_query_log(action, detail, level, raw_data)`
- 存储路径：`data/query/query_log.json`（最多200条）
- 前端定时拉取：3秒间隔，`/api/query/log`
- 支持按类型筛选：全部/设备查询/任务查询

## 全链路调试面板

- 设备号查询时始终显示"查询调试信息"按钮
- 展示4步链路：step1找任务单号 → step2查主任务 → step3查子任务 → step4查设备状态
- 每步显示请求URL、请求体、响应体、HTTP状态码、耗时

## 注意事项

1. **CSS 变量系统**：页面使用 `--card-bg`、`--detail-card-bg`、`--border-color` 等变量，支持亮色/暗黑主题
2. **暗黑模式 bg-light 覆盖**：已添加 `[data-bs-theme="dark"] .bg-light` 覆盖规则
3. **跨环境任务**：设备只在一个服务器在线是正常的，不显示"状态不一致"警告
4. **firstOk 逻辑**：排除下线/离线后取有效状态，用于主状态展示
5. **sprite 图**：使用裁剪后的 `rcsagv_lift.png`，不要直接使用 1280×1280 大图

## ds 说
- 2026-05-09: 深度查询页面完成重大改版：设备状态卡片改为卡片式服务器面板、sprite 图标按状态动态切换、子任务卡片添加设备状态小图标、修复最近查询设备历史、step2失败时写入操作日志并返回调试信息
- sprite 颜色映射已按 rcsagvpng.md 第8节修正：col 0蓝 1绿 2红 3橙 4灰 5紫
- Offline/Downlined 的 badge 和 agv-icon 背景色从红色改为灰色（secondary/pending）
- 子任务设备图标通过参数传递 deviceStatuses 确保数据可用，不依赖全局变量
- 2026-05-22: 三大优化：1) 设备号查询 step1 改为 pageSize=5，返回 recent_tasks 列表，前端新增 renderRecentTaskTabs 任务标签栏 + switchDeviceTask 切换；2) 任务重发逻辑修改：非状态8和6都有重发按钮，重发前先调用远端 POST /ics/out/task/cancelTask 取消接口；3) 按 orderId 查询改为调用新 API /api/query/order_tasks，展示设备状态卡片。新增 _deep_query_by_order_id 辅助函数复用 step2~step4 逻辑。
- 2026-05-25: 重发流程增加设备预占步骤：预占 POST /enableAGV（取消前一次+取消后一次）→ 取消任务 → 修改数据库。步骤顺序优化：前置检查→状态检查→预占→取消→预占→生成ID→修改状态。新增 SSE 实时动画：后端新增 resend_cross_task_stream 生成器 + SSE 端点 /api/task/resend/stream，前端新增重发进度模态框，每步显示耗时和状态（🔄 ✅ ❌），完成后自动刷新。

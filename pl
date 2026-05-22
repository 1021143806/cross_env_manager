# 查询界面优化方案

## 需求概述

1. **设备号查询列出最近几条任务**：step1 查询多条，默认展示第一条，允许用户快速切换
2. **任务重发逻辑修改**：非状态8和6都有重发按钮，重发前先调用远端取消接口
3. **按 orderId 查询展示设备状态**：任务单号查询也展示设备实时状态卡片

---

## 需求1：设备号查询 - 列出最近几条任务

### 现状
- `routes/task_routes.py:291-301`：step1 按设备号查询 `pageSize: 1`，只取一条
- 找到后直接执行 step2~step4 深度查询并返回

### 目标
- step1 改为 `pageSize: 5`，收集该设备最近的5条任务
- 返回 `recent_tasks` 列表 + 第一条的完整深度查询结果
- 前端顶部显示任务标签栏，点击切换

### 后端改动

#### 文件：`routes/task_routes.py` → `api_device_tasks()`

1. step1 改为 `pageSize: 5`，遍历所有优先级状态，收集最多5条任务
2. 返回结果新增 `recent_tasks` 字段：
   ```json
   {
     "recent_tasks": [
       {
         "orderId": "xxx",
         "deviceCode": "xxx",
         "taskStatus": 6,
         "taskStatusName": "执行中",
         "createTime": "2025-01-01 12:00:00",
         "modelProcessName": "搬运模板A",
         "areaId": 1
       }
     ],
     // 以下为第一条任务的深度查询结果（现有字段）
     "success": true,
     "device_num": "...",
     "order_id": "...",
     "mainTask": {...},
     "subTasks": [...],
     "device_statuses": [...],
     "query_debug": {...}
   }
   ```
3. 默认对 `recent_tasks[0]` 执行 step2~step4

#### 新增 API：`POST /api/query/device_task_detail`

- 入参：`{ order_id: "xxx" }`
- 复用 step2~step4 逻辑，返回与 `api_device_tasks` 相同结构的深度查询结果
- 用于用户点击切换任务时

### 前端改动

#### 文件：`templates/query/unified_home.html`

1. **新增函数 `renderRecentTaskTabs(recentTasks, currentOrderId)`**：
   - 在结果区顶部渲染横向标签栏
   - 每条显示：状态badge + 创建时间 + 模板名称（截断）
   - 当前选中高亮，点击触发切换

2. **修改 `executeQuery()` 设备号查询分支**：
   - 解析 `data.recent_tasks`
   - 存储到 `window._recentTasks`
   - 调用 `renderRecentTaskTabs()` 渲染标签栏
   - 然后正常渲染第一条结果

3. **新增函数 `switchDeviceTask(orderId)`**：
   - 调用 `/api/query/device_task_detail`
   - 重新渲染结果区

---

## 需求2：任务重发逻辑修改

### 现状
- 前端 `renderSubTaskCard`（行2130-2155）：
  - status=3 → "重发"按钮
  - status=7 → "重发"按钮
  - status=4/6/9 → "强制重发"按钮
  - status=5 → "重发中..."（禁用）+ "异常完成"
- 后端 `resend_cross_task()`（行463-623）：
  - 允许重发的子任务状态：3,4,6,7,9
  - 允许重发的大模板状态：3,5,6,7,9
  - 无取消远端任务步骤

### 目标
- 非状态8（已完成）和状态6（执行中）的任务都有重发按钮
- 重发前先调用远端服务器取消任务接口
- 远端取消接口：`POST http://{server_ip}:7000/ics/out/task/cancelTask`
  - 请求体：`[{"orderId": "{sub_order_id}", "destPosition": ""}]`
  - 参考：`routes/dispatch_routes.py:2291-2319` `_cancel_empty_task()`

### 后端改动

#### 文件：`modules/query/task_query_extended.py` → `resend_cross_task()`

1. **新增步骤0：调用远端取消接口**
   - 从 `fy_cross_task_detail` 查询 `service_url` 获取服务器地址
   - 调用 `POST http://{server_ip}:7000/ics/out/task/cancelTask`
   - 请求体：`[{"orderId": "{sub_order_id}", "destPosition": ""}]`
   - 取消失败则返回错误，不继续重发

2. **放宽状态检查**：
   - 子任务允许重发的状态：1,2,3,4,5,7,9,10（排除6和8）
   - 大模板允许重发的状态：1,2,3,4,5,7,9,10（排除6和8）

3. **状态6特殊处理**：
   - 状态6（执行中）不允许重发，因为任务正在远端执行
   - 必须先取消才能重发

### 前端改动

#### 文件：`templates/query/unified_home.html` → `renderSubTaskCard()`

修改操作按钮区（行2130-2155）：

```javascript
// 新逻辑：
// status != 8 && status != 6 → 显示重发按钮
// status == 5 → 额外显示"异常完成"按钮
// status == 6 → 不显示重发按钮（执行中）
// status == 8 → 不显示重发按钮（已完成）

${status != 8 && status != 6 ? 
    `<button class="btn btn-sm btn-outline-warning" onclick="resendTask('${subOrderId}', '${orderId}', ${taskSeq})" title="重发任务">
        <i class="bi bi-arrow-repeat"></i> 重发
    </button>` : ''}
${status == 5 ? 
    `<button class="btn btn-sm btn-outline-danger" onclick="forceCompleteTask('${subOrderId}', '${orderId}', ${taskSeq})" title="异常完成（仅将子任务状态置为3）">
        <i class="bi bi-check-circle"></i> 异常完成
    </button>` : ''}
```

---

## 需求3：按 orderId 查询展示设备状态

### 现状
- 按任务单号查询走前端 `performDeepQuery()`（行1075），多次直接 fetch 远端 API
- 不包含设备状态查询步骤

### 目标
- 按 orderId 查询时，也从子任务中提取 device_code，查询设备实时状态
- 展示设备状态卡片（与设备号查询一致）

### 后端改动

#### 新增 API：`POST /api/query/order_tasks`

- 入参：`{ order_id: "xxx", server_ip: "10.68.2.32" }`
- 流程：
  1. step2：查询主任务（`/crossTask/query`）
  2. step3：查询子任务（`/crossTask/detail`）
  3. step4：从子任务提取 device_code，查询设备实时状态
  4. enrich 补充本地数据库字段
- 返回结构与 `api_device_tasks` 一致（含 `device_statuses`）

### 前端改动

#### 文件：`templates/query/unified_home.html`

1. **修改 `executeQuery()` 任务单号查询分支**：
   - 改为调用 `/api/query/order_tasks` 替代前端 `performDeepQuery()`
   - 结果中包含 `deviceStatuses`，自动渲染设备状态卡片

2. **保留 `performDeepQuery()` 作为降级方案**（可选）

---

## 涉及文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `routes/task_routes.py` | 修改 + 新增 | 修改 `api_device_tasks`，新增 `api_device_task_detail`、`api_order_tasks` |
| `modules/query/task_query_extended.py` | 修改 | 修改 `resend_cross_task` 增加取消步骤，放宽状态检查 |
| `templates/query/unified_home.html` | 修改 | 新增任务标签栏、修改重发按钮逻辑、修改任务单号查询流程 |

---

## 实施顺序

1. 先改后端（`task_query_extended.py` 重发逻辑 + `task_routes.py` 新 API）
2. 再改前端（`unified_home.html` 三个需求的 UI 改动）
3. 测试验证

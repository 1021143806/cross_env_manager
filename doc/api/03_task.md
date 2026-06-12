# 3. 任务查询 & 重发 API

## 3.1 任务查询

### 3.1.1 获取任务组信息
```
GET /api/task_group/<order_id>
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| order_id | string | 是 | 任务单号（路径参数） |
| server_ip | string | 否 | 服务器 IP |

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
  "details": [{"id": 123, "tg_id": 6413848, "task_seq": 1, "status": 8}],
  "source": "local"
}
```

### 3.1.2 后端代理查询
```
POST /addtask/query
```
Flask 统一代理 ICS 请求，浏览器不直接暴露服务器地址。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| orderId | string | 否 | 订单号（与 shelfNum/deviceNum 三选一） |
| shelfNum | string | 否 | 货架号 |
| deviceNum | string | 否 | 设备号 |

**路由规则（按 orderId 前缀）：**
- `RLLR_` 前缀 → 非跨环境 API `:7000/ics/out/task/getTaskOrderStatus`
- `CEM_` 前缀 → 先查 `:8315/crossTask/query`，未找到则回退辊筒 API

## 3.2 任务重发

### 3.2.1 重发跨环境任务
```
POST /api/task/resend
```
> ⚠️ 此接口直接修改生产数据库，请谨慎使用。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| orderId | string | 是 | 大模板任务单号 |
| subOrderId | string | 是 | 子任务 ID（当前） |
| taskSeq | int | 是 | 子任务序号 |
| serverIp | string | 否 | 数据库服务器 IP |

**重发逻辑：**

| 大模板状态 | 子模板状态 | 行为 |
|-----------|-----------|------|
| 3（已取消） | 3（已取消） | 大模板改为5，子模板改为5，sub_order_id+1 |
| 5（重发中） | 7（失败） | 仅子模板改为5，sub_order_id+1 |
| 7（任务失败） | 7（失败） | 仅子模板改为5，sub_order_id+1 |
| 6/9（已下发） | 4/6/9 | 大模板改为5，子模板改为5，sub_order_id+1 |

### 3.2.2 异常完成
```
POST /api/task/force_complete
```
仅修改子模板状态为 3（已取消），不修改大模板和 sub_order_id。
适用于重发中（status=5）卡住的子任务。
